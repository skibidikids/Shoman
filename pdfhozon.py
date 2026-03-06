import os
import time
import base64
import json
import re
from urllib.parse import urlparse, urldefrag
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 設定 ---
# PDFを保存するフォルダ
OUTPUT_DIR = "診断の手引き"
# 疾患群別一覧ページのURL
BASE_URL = "https://www.shouman.jp/disease/search/group/"

def setup_driver():
    """
    PDF印刷用に設定されたChromeドライバをセットアップします。
    """
    chrome_options = Options()
    # ヘッドレスモード（画面を表示しない）で実行
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    # 印刷設定（背景のグラフィックなどを有効にする）
    settings = {
        "recentDestinations": [{
            "id": "Save as PDF",
            "origin": "local",
            "account": "",
        }],
        "selectedDestinationId": "Save as PDF",
        "version": 2,
        "isHeaderFooterEnabled": False, # ヘッダー・フッター（URLや日付）を消す
        "isCssBackgroundEnabled": True  # 背景色・画像を印刷する
    }
    chrome_options.add_argument(f'--appState={json.dumps(settings)}')

    # WebDriverの起動
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def print_page_to_pdf(driver, url, output_dir, file_id):
    """
    指定されたURLを開き、PDFとして保存します。
    """
    try:
        driver.get(url)
        # ページの読み込み待機（bodyタグが表示されるまで）
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # レンダリングが完全に終わるまで少し待機（画像やスタイル崩れ防止）
        time.sleep(2)

        # ページタイトルを取得してファイル名にする
        page_title = driver.title
        
        # 不要な文言を削除して疾患名のみにする
        for text in ["診断の手引き - 小児慢性特定疾病情報センター", " - 小児慢性特定疾病情報センター", "診断の手引き"]:
            page_title = page_title.replace(text, "")
        page_title = page_title.strip()

        # サイト名などが付いている場合は除去（例: "病名 | サイト名" -> "病名"）
        if "|" in page_title:
            page_title = page_title.split("|")[0].strip()
        
        # ファイル名に使えない文字を除去
        safe_title = re.sub(r'[\\/:*?"<>|]', '', page_title)
        # 長すぎる場合はカット
        if len(safe_title) > 50:
            safe_title = safe_title[:50]
            
        # ファイル名: ID_病名.pdf
        filename = f"{file_id}_{safe_title}.pdf"
        output_path = os.path.join(output_dir, filename)

        # Chrome DevTools Protocol (CDP) を使用してPDF出力コマンドを実行
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "landscape": False,
            "displayHeaderFooter": False,
            "printBackground": True,
            "preferCSSPageSize": True,
        })
        
        # バイナリデータをファイルに書き出し
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(result['data']))
        print(f"[保存完了] {filename}")
        return True
    except Exception as e:
        print(f"[エラー] {url} の保存に失敗しました: {e}")
        return False

def get_all_guideline_urls(driver):
    """
    サイトを巡回して「診断の手引き」のURLリストを取得します。
    """
    target_urls = []
    
    print("疾患群一覧ページにアクセスしています...")
    driver.get(BASE_URL)
    time.sleep(1)

    # 1. 疾患群（大分類）のリンクを取得
    # URLに '/disease/search/group/' を含み、かつ詳細ページへのリンクと思われるものを抽出
    # ※サイト構造が変わった場合はここのセレクタ調整が必要です
    group_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/disease/search/group/')]")
    
    # 重複を除去しつつURLリストを作成
    group_urls = set()
    for elem in group_elements:
        href = elem.get_attribute("href")
        if href:
            # URLの末尾(#xx)を除去して重複をなくす
            href, _ = urldefrag(href)
            if href != BASE_URL:
                group_urls.add(href)
    
    print(f"{len(group_urls)} 件の疾患群が見つかりました。各ページをスキャンします。")

    # 2. 各疾患群ページから「診断の手引き」ボタンを探す
    for i, g_url in enumerate(group_urls, 1):
        print(f"[{i}/{len(group_urls)}] スキャン中: {g_url}")
        try:
            driver.get(g_url)
            time.sleep(2) # 読み込み待ち時間を少し増やす
            
            # 「診断の手引き」というテキストを持つリンクを探す
            # text()だとタグ内のテキスト(span等)が拾えない場合があるため . を使用
            links = driver.find_elements(By.XPATH, "//a[contains(., '診断の手引き')]")
            
            count_in_page = 0
            for link in links:
                href = link.get_attribute("href")
                if href and "/instructions/" in href:
                    target_urls.append(href)
                    count_in_page += 1
            
            print(f"  -> {count_in_page} 件の手引きが見つかりました。")
            
        except Exception as e:
            print(f"  -> ページの読み込みエラー: {e}")

    return sorted(list(set(target_urls))) # 重複排除し、URL順（ID順）にソートして返す

def main():
    # 保存先ディレクトリ作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    driver = setup_driver()
    
    try:
        # ステップ1: URLの収集
        # 全自動で収集する場合
        print("--- URLの収集を開始します ---")
        urls = get_all_guideline_urls(driver)
        print(f"合計 {len(urls)} 件の診断の手引きを保存します。")
        
        # ステップ2: PDF保存
        print("--- PDF保存を開始します ---")
        for i, url in enumerate(urls, 1):
            # ファイル名をURLの末尾（例: 01_01_001）から生成
            # 必要であればここで疾患名などをファイル名に含める工夫も可能です
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            file_id = path_parts[-1] if path_parts else f"doc_{i}"
            
            # 既に同じIDのファイルがあるか確認（ファイル名が変わるためIDで検索）
            # フォルダ内のファイル一覧を取得
            existing_files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(f"{file_id}_") and f.endswith(".pdf")]
            
            if existing_files:
                print(f"[{i}/{len(urls)}] スキップ（保存済み）: {existing_files[0]}")
                continue
            
            print(f"[{i}/{len(urls)}] 保存中: {url}")
            print_page_to_pdf(driver, url, OUTPUT_DIR, file_id)
            
            # サーバーへの負荷を考慮して少し待機
            time.sleep(1)

    finally:
        driver.quit()
        print("処理が完了しました。")

if __name__ == "__main__":
    main()
