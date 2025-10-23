from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import re
import os
import time # 导入 time 模块用于等待

def extract_and_save_download_links(url, output_filename="links.txt"):
    """
    使用 Selenium 提取页面中的下载链接、节目名称和日期，并按指定格式写入文件。
    :param url: 目标网页的 URL。
    :param output_filename: 输出文件名。
    """
    download_data = [] # 存储 (节目名称 + 日期, 下载链接) 的元组

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if not chromedriver_path:
        print("CHROMEDRIVER_PATH 环境变量未设置，尝试使用 ChromeDriverManager().install()")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            chromedriver_path = ChromeDriverManager().install()
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
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody tr"))
        )
        print("页面加载完成，开始提取链接...")

        # --- 提取当前页面的数据 ---
        def extract_current_page_data():
            current_page_data = []
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
                except Exception as e:
                    # 某些行可能没有完整的下载信息，跳过
                    print(f"处理行时发生错误: {e}")
                    continue
            return current_page_data

        download_data.extend(extract_current_page_data())

        # --- 分页处理 ---
        current_page_num = 1
        while True:
            try:
                # 寻找下一页按钮
                # GitHub Actions 的日志显示 page-next 按钮可能不可点击，
                # 我们需要确保它是可点击的
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#Pagination .page-next"))
                )

                # 检查下一页按钮是否为"尾页"或已禁用 (这里简单判断 class 中是否包含 'disabled' 或 'page-last')
                # 根据你提供的 HTML，"尾页"按钮也有 'page-last' class
                # 我们的目标是找到“下一页”按钮，如果它存在且不是尾页
                if "page-last" in next_button.get_attribute("class") or "disabled" in next_button.get_attribute("class"):
                    print("已到达最后一页或下一页按钮不可用。")
                    break

                # 实际的下一页按钮可能在分页数字中，我们假设点击下一个数字
                # 或者直接找到 class 为 page-next 的元素
                next_page_link_css = f'#Pagination a.num_page + a.num_page' # 尝试定位当前选中页的下一个数字页
                
                # 更稳健的方法是找到当前选中的页码，然后尝试点击下一个页码
                current_checked_page_element = driver.find_element(By.CSS_SELECTOR, "#Pagination .num_page.checked_num")
                next_page_element = current_checked_page_element.find_element(By.XPATH, "./following-sibling::a[contains(@class, 'num_page')]")

                if next_page_element:
                    next_page_element.click()
                    current_page_num += 1
                    print(f"点击下一页，当前第 {current_page_num} 页")
                    time.sleep(3) # 等待新页面内容加载，可能需要更长时间

                    # 再次等待新的数据加载完成
                    WebDriverWait(driver, 15).until(
                        EC.staleness_of(rows[0]) # 等待旧的行元素从DOM中消失
                    )
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody tr"))
                    )

                    download_data.extend(extract_current_page_data())
                else:
                    print("未找到下一个数字页链接，结束分页。")
                    break

            except Exception as e:
                print(f"处理分页时发生错误或已到最后一页: {e}")
                break

    except Exception as e:
        print(f"主程序发生错误: {e}")
    finally:
        if driver:
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
page_url = "https://www.radio.cn/pc-portal/sanji/zhibo_2.html?channelname=0&name=1395673&title=radio#"

if __name__ == "__main__":
    extract_and_save_download_links(page_url, "links.txt")        python extract_radio_links.py # 替换为你的 Python 脚本文件名

    - name: Upload links.txt artifact
      uses: actions/upload-artifact@v4
      with:
        name: extracted-links
        path: links.txt # 指定要上传的文件
        retention-days: 7 # 保留 Artifact 的天数
