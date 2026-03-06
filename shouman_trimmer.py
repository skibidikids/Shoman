# -*- coding: utf-8 -*-

import fitz  # PyMuPDF
import os

# --- 設定 ---
INPUT_DIR = "診断の手引き"
OUTPUT_DIR = "診断の手引き_加工後"
TARGET_PHRASE = "関連資料"    # 検索するキーワード（"---関連資料---"など適宜変更してください）

# ページ上端から何ポイント以内なら「ページ丸ごと関連資料」と判定するか（微調整用）
# ※PDFの余白設定によりますが、大体50〜70くらいが目安です。
TOP_THRESHOLD = 70

def process_pdfs():
    # 出力フォルダがなければ作成
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # フォルダ内の全PDFを処理
    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith(".pdf"):
            continue

        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        doc = fitz.open(input_path)
        cut_at_page = None  # 削除を開始するページ番号

        # 全ページをスキャン
        for page_num in range(len(doc)):
            page = doc[page_num]
            # キーワードの座標を検索
            text_instances = page.search_for(TARGET_PHRASE)

            if text_instances:
                # 最初に見つかったキーワードの上端Y座標を取得
                y0 = text_instances[0].y0
                
                if y0 < TOP_THRESHOLD:
                    # キーワードがページの最上部にある場合 → このページから削除
                    cut_at_page = page_num
                else:
                    # キーワードが中段・下段にある場合 → このページは残し、次のページから削除
                    cut_at_page = page_num + 1
                break # 見つけたら以降のページはスキャン不要なのでループを抜ける

        # PDFの保存処理
        if cut_at_page is not None and cut_at_page < len(doc):
            # 抽出用の新しいPDFを作成
            new_doc = fitz.open()
            # 0ページ目から、削除開始ページの直前までをコピー
            if cut_at_page > 0:
                new_doc.insert_pdf(doc, from_page=0, to_page=cut_at_page - 1)
                new_doc.save(output_path)
                print(f"✂️ カット完了: {filename} (ページ {cut_at_page + 1} 以降を削除)")
            else:
                print(f"⚠️ スキップ: {filename} (1ページ目の最上部から関連資料です)")
            new_doc.close()
        else:
            # キーワードが見つからなかった場合、または最終ページの末尾にあった場合はそのまま保存
            doc.save(output_path)
            print(f"✅ 変更なし: {filename}")
        
        doc.close()

if __name__ == "__main__":
    print("処理を開始します...")
    process_pdfs()

    print("すべての処理が完了しました！")
