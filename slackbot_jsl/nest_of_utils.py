import os, json
from datetime import datetime

def write_text_to_file_with_timestamp(file_path, text, timestamp=False, encoding='utf-8'):
    """
    指定されたファイルパスにテキストを書き込む関数です。timestampがTrueの場合、ファイル名にタイムスタンプを追加します。

    引数:
    - filepath (str): テキストを書き込むファイルのパス。
    - text (str): ファイルに書き込むテキスト。
    - timestamp (bool, optional): ファイル名にタイムスタンプを追加するかどうか。デフォルトはFalse。
    - encoding (str): 保存エンコード
    """
    if timestamp:
        # ファイルパスを拡張子前と拡張子に分割
        base, ext = os.path.splitext(file_path)
         # 現在の日時を「_yyyyMMdd_hh24mmss」形式で取得
        now = datetime.now().strftime('_%Y%m%d_%H%M%S')
        # タイムスタンプをファイル名に追加
        file_path = f"{base}{now}{ext}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # テキストをutf-8でファイルに書き込み
    with open(file_path, 'w', encoding=encoding) as file:
        file.write(text)

    # ファイル作成完了のメッセージ
    print(f"ファイル「{file_path}」を作成したよ😊✨！")


def load_json_files(files: list[str], n: int, islast: bool = False) -> list[dict]:
    """
    指定されたファイルリストから上位(下位)N件のファイルを読み込み、辞書に変換します。

    Args:
        files (List[str]): ファイルパスのリスト
        n (int): 読み込むファイルの最大数
        islast (bool): 下位をとる
    Returns:
        list[dict]: 読み込んだJSONファイルの内容を辞書に変換したリスト
    """
    n = n if not islast else -n
    top_n_files_content = []
    for file_path in sorted(files)[n:]:
        with open(file_path, 'r', encoding='utf-8') as file:
            top_n_files_content.append(json.load(file))
    return top_n_files_content


def filter_dic(dic:dict, keylist:list[str]) -> dict:
    '''
    キーリスト(ホワイトリスト)に従い不要なキーを削除
    '''
    return {k: dic[k] for k in keylist if k in dic}


def read_all_text_from_file(file_path: str, encoding: str = "utf-8") -> tuple[bool, str]:
    """
    指定されたファイルパスのテキストを読み込み、読み込みの成否とテキスト内容を返します。

    :param file_path: 読み込むファイルのパス
    :param encoding: ファイルのエンコーディング デフォルトはutf-8 
    :return: (読み込みの成否を表すブール値, 読み込んだテキスト内容または空文字列)
    """
    try:
        # ファイルを指定されたエンコーディングで開き、内容を読み込む
        with open(file_path, "r", encoding=encoding) as file:
            content = file.read()
        # 成功した場合はTrueと読み込んだ内容を返す
        return True, content
    except Exception as e:
        # エラーが発生した場合は、Falseと空文字列を返す
        print(f"エラーが発生しました: {e}")
        return False, ""

