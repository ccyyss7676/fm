from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import re
import os
import time

def extract_and_save_download_links(url, output_filename="links.txt"):
    """
    使用 Selenium 提取页面中的下载链接、节目名称和日期，并按指定格式写入文件。
    此版本已调整为在 GitHub Actions 的无头模式下运行，并增强了分页处理。
    
    :param url: 目标网页的 URL。
    :param output_filename: 输出文件名。
    """
    download_data = [] # 存储 (节目名称 + 日期, 下载链接) 的元组

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless") # 无头模式
    chrome_options.add_argument("--no-sandbox") # 在 CI/CD 环境中通常需要
    chrome_options.add_argument("--disable-dev-shm-usage") # 解决 Docker 或 CI 环境内存问题
    chrome_options.add_argument("--window-size=1920,1080") # 设置窗口大小，确保所有元素可见
    chrome_options.add_argument("--start-maximized") # 最大化窗口
    chrome_options.add_argument("--disable-gpu") # 某些Linux环境可能需要禁用GPU

    # 获取 ChromeDriver 路径。在 GitHub Actions 中，我们将通过环境变量传递
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if not chromedriver_path:
        print("CHROMEDRIVER_PATH 环境变量未设置。尝试使用 ChromeDriverManager().install()")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            chromedriver_path = ChromeDriverManager().install()
            print(f"ChromeDriverManager 自动安装到: {chromedriver_path}")
        except Exception as e:
            print(f"自动安装 ChromeDriver 失败: {e}")
            print("请确保 ChromeDriver 已正确安装并可被访问，或者设置 CHROMEDRIVER_PATH 环境变量。")
            return

    service = ChromeService(executable_path=chromedriver_path)
    driver = None
    try:
        print(f"正在使用 ChromeDriver 路径: {chromedriver_path}")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print(f"正在访问页面: {url}")
        driver.get(url)

        # 等待页面加载完成，特别是等待下载链接所在的元素出现
        print("等待初始页面加载...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody tr"))
        )
        print("初始页面加载完成，开始提取链接...")

        # --- 提取当前页面的数据 ---
        def extract_current_page_data():
            current_page_data = []
            try:
                # 重新查找行元素，以防 StaleElementReferenceException
                rows = driver.find_elements(By.CSS_SELECTOR, "#programList tbody tr")
                for row in rows:
                    try:
                        # 节目日期在第一个 td
                        date_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)")
                        program_date = date_element.text.strip()

                        # 节目名称在第二个 td 的 <a> 标签中
                        name_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
                        program_name = name_element.text.strip()

                        # 下载链接在第三个 td 的 <a> 标签的 onclick 属性中
                        download_link_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(3) a[onclick^='downLiveRecord']")
                        onclick_attr = download_link_element.get_attribute("onclick")

                        if onclick_attr:
                            match = re.search(r"downLiveRecord\('([^']*)'", onclick_attr)
                            if match:
                                download_url = match.group(1)
                                # 拼接成 "节目名称日期" 作为 item_title
                                item_title = f"{program_name}{program_date}"
                                current_page_data.append((item_title, download_url))
                    except NoSuchElementException:
                        # 某些行可能缺少下载链接或名称，跳过
                        # print("警告: 发现缺少关键元素的行，已跳过。")
                        continue
                    except Exception as e_row:
                        print(f"处理行时发生意外错误: {e_row}")
                        continue
            except Exception as e_extract_page:
                print(f"提取当前页面数据时发生错误: {e_extract_page}")
            return current_page_data

        download_data.extend(extract_current_page_data())

        # --- 分页处理 ---
        current_page_num = 1
        while True:
            try:
                # 在每次循环开始时获取当前页面的行元素，用于 staleness_of 检查
                # 注意：这里获取的是当前页面的元素，用于判断页面是否刷新
                initial_rows_for_staleness = driver.find_elements(By.CSS_SELECTOR, "#programList tbody tr")
                if not initial_rows_for_staleness:
                    print("当前页面没有找到节目行元素，可能已是最后一页或页面结构改变，停止分页。")
                    break
                
                # 尝试点击下一个数字页码
                next_page_element_to_click = None
                try:
                    current_checked_page_element = driver.find_element(By.CSS_SELECTOR, "#Pagination .num_page.checked_num")
                    # 查找当前选中页码的下一个兄弟元素，且它也是一个数字页码
                    next_page_candidates = current_checked_page_element.find_elements(By.XPATH, "./following-sibling::a[contains(@class, 'num_page')]")
                    if next_page_candidates:
                        next_page_element_to_click = next_page_candidates[0]
                except NoSuchElementException:
                    # 没有找到当前选中的页码或者下一个数字页码
                    pass # 继续尝试点击“下一页”文本按钮

                if next_page_element_to_click:
                    print(f"尝试点击页码: {next_page_element_to_click.text}")
                    next_page_element_to_click.click()
                else:
                    # 如果没有找到下一个数字页码，尝试点击“下一页”文本按钮
                    try:
                        next_text_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "#Pagination .page-next"))
                        )
                        # 检查“下一页”按钮是否是尾页或已禁用
                        if "page-last" in next_text_button.get_attribute("class") or "disabled" in next_text_button.get_attribute("class"):
                             print("已到达最后一页或'下一页'按钮不可用，停止分页。")
                             break
                        next_text_button.click()
                    except TimeoutException:
                        print("未找到可点击的'下一页'按钮，可能已是最后一页或加载错误，停止分页。")
                        break
                    except Exception as e_text_btn:
                        print(f"点击'下一页'文本按钮时发生错误: {e_text_btn}")
                        break

                current_page_num += 1
                print(f"成功点击下一页，当前第 {current_page_num} 页。")
                time.sleep(3) # 给予页面足够的时间加载新内容和执行JS

                # 等待页面内容更新
                # 1. 等待旧的行元素从DOM中消失
                WebDriverWait(driver, 15).until(
                    EC.staleness_of(initial_rows_for_staleness[0])
                )
                # 2. 等待新的行元素出现
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody tr"))
                )
                # 3. 再次等待新的下载链接元素出现，确保页面完全稳定
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody a[onclick^='downLiveRecord']"))
                )

                download_data.extend(extract_current_page_data())

            except StaleElementReferenceException:
                print("StaleElementReferenceException: 元素已过时，尝试重新获取。")
                # 这种情况通常发生在页面更新后尝试使用旧的元素引用。
                # 在循环顶部重新获取 initial_rows_for_staleness 可以缓解。
                # 如果频繁发生，可能需要更长的 sleep 或更复杂的等待逻辑。
                continue # 继续下一次循环，重新尝试

            except TimeoutException:
                print("等待新页面内容加载超时，可能已是最后一页或网络问题，停止分页。")
                break
            except Exception as e_page_loop:
                print(f"分页循环中发生意外错误: {e_page_loop}")
                break

    except Exception as e_main:
        print(f"主程序执行过程中发生错误: {e_main}")
    finally:
        if driver:
            print("关闭浏览器。")
            driver.quit()

    # 将提取到的数据写入文件
    if download_data:
        with open(output_filename, "w", encoding="utf-8") as f:
            for title, link in download_data:
                f.write(f"{title} ：{link}\n")
        print(f"\n成功提取 {len(download_data)} 条链接并写入到 {output_filename}")
    else:
        print("\n未能提取到任何下载链接。")

# 页面URL
page_url = "https://www.radio.cn/pc-portal/sanji/zhibo_2.html?channelname=0&name=1395673&title=radio#" # 修改为你的目标URL

if __name__ == "__main__":
    extract_and_save_download_links(page_url, "links.txt")
