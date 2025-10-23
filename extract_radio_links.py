from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import re
import os # 导入 os 模块来获取环境变量

def extract_download_links_selenium(url):
    """
    使用 Selenium 提取页面中的下载链接。
    此版本已调整为在 GitHub Actions 的无头模式下运行。
    :param url: 目标网页的 URL。
    :return: 包含下载链接的列表。
    """
    download_links = []

    # 配置 Chrome 选项，使其在无头模式下运行
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless") # 无头模式
    chrome_options.add_argument("--no-sandbox") # 在 CI/CD 环境中通常需要
    chrome_options.add_argument("--disable-dev-shm-usage") # 解决 Docker 或 CI 环境内存问题

    # 获取 ChromeDriver 路径。在 GitHub Actions 中，我们将通过环境变量传递
    # 或者让 webdriver_manager 自动管理
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if not chromedriver_path:
        # 如果环境变量未设置，尝试让 webdriver_manager 自动下载和获取路径
        # 这要求你已经在 actions 中安装了 webdriver-manager
        print("CHROMEDRIVER_PATH 环境变量未设置，尝试使用 ChromeDriverManager().install()")
        from webdriver_manager.chrome import ChromeDriverManager
        chromedriver_path = ChromeDriverManager().install()

    service = ChromeService(executable_path=chromedriver_path)
    driver = None
    try:
        print(f"正在使用 ChromeDriver 路径: {chromedriver_path}")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print(f"正在访问页面: {url}")
        driver.get(url)

        # 等待页面加载完成，特别是等待下载链接所在的元素出现
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#programList tbody a[onclick^='downLiveRecord']"))
        )
        print("页面加载完成，开始提取链接...")

        # 提取当前页面的所有下载链接
        download_elements = driver.find_elements(By.CSS_SELECTOR, "a[onclick^='downLiveRecord']")

        for element in download_elements:
            onclick_attr = element.get_attribute("onclick")
            if onclick_attr:
                match = re.search(r"downLiveRecord\('([^']*)'", onclick_attr)
                if match:
                    download_url = match.group(1)
                    download_links.append(download_url)
        
        # 你的分页处理逻辑可以在这里添加，确保它也适用于无头模式
        # ... (与之前相同的分页逻辑，注意等待元素出现)

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if driver:
            driver.quit() # 确保关闭浏览器

    return download_links

# 页面URL
page_url = "https://www.radio.cn/pc-portal/sanji/zhibo_2.html?channelname=0&name=1395673&title=radio#"

if __name__ == "__main__":
    download_links = extract_download_links_selenium(page_url)

    if download_links:
        print("\n提取到的所有下载链接:")
        for link in download_links:
            print(link)
    else:
        print("未能提取到下载链接。请检查 WebDriver 配置或页面元素定位是否正确。")
