name: Extract Download Links

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  extract-links:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.x'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install selenium requests webdriver-manager # 确保安装 webdriver-manager

    - name: Install Google Chrome
      run: |
        sudo apt-get update
        sudo apt-get install -y google-chrome-stable

    - name: Run Python script to extract links
      run: |
        # webdriver_manager 会自动下载 ChromeDriver，并返回其路径
        # 我们将此路径设置为环境变量，供Python脚本使用
        export CHROMEDRIVER_PATH=$(python -c "from webdriver_manager.chrome import ChromeDriverManager; print(ChromeDriverManager().install())")
        python extract_radio_links.py # 替换为你的 Python 脚本文件名

    - name: Upload links.txt artifact
      uses: actions/upload-artifact@v4
      with:
        name: extracted-links
        path: links.txt # 指定要上传的文件
        retention-days: 7 # 保留 Artifact 的天数
