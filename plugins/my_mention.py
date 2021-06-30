import json
import sqlite3
import re
import pandas as pd
import requests
import datetime
import urllib.request
from pyzbar.pyzbar import decode
from PIL import Image
import shutil
from slackbot.bot import respond_to     # @botname: で反応するデコーダ
from slackbot.bot import default_reply  # 該当する応答がない場合に反応するデコーダ
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# @respond_to('string')     bot宛のメッセージ
#                           stringは正規表現が可能 「r'string'」
# @listen_to('string')      チャンネル内のbot宛以外の投稿
#                           @botname: では反応しないことに注意
#                           他の人へのメンションでは反応する
#                           正規表現可能
# @default_reply()          DEFAULT_REPLY と同じ働き
#                           正規表現を指定すると、他のデコーダにヒットせず、
#                           正規表現にマッチするときに反応
#                           ・・・なのだが、正規表現を指定するとエラーになる？

# message.reply('string')   @発言者名: string でメッセージを送信
# message.send('string')    string を送信
# message.react('icon_emoji')  発言者のメッセージにリアクション(スタンプ)する
#                               文字列中に':'はいらない

# SlackBotのトークン
slack_token = "Slack Token"
client = WebClient(token=slack_token)
# デフォルトの表紙画像
default_image = "image url"
# 接続先のDBを指定
con = sqlite3.connect("book.db", check_same_thread=False, isolation_level=None)
# カーソルオブジェクトの生成
cur = con.cursor()
# SELECT文の実行
# 0 id         ：データID
# 1 user_id    ：ユーザーID
# 2 title      ：本のタイトル
# 3 author     ：著者
# 4 publisher  ：出版社
# 5 status     ：読書状態
# 6 date       ：登録日時
# 7 url        ：本の表紙のURL
# 8 isbn       ：ISBNコード
# 9 summary    ：あらすじ
cur.execute('''CREATE TABLE IF NOT EXISTS book_dana(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id varchar(100),
    title varchar(100) NOT NULL,
    author varchar(100),
    publisher varchar(100),
    status varchar(100),
    date date,
    url varchar(10000),
    isbn varchar(30),
    summary varchar(500))''')
# insert文の実行
# 初期状態の設定
summ1 = """迷宮都市オラリオ-『ダンジョン』と通称される壮大な地下迷宮を保有する巨大都市。
    未知という名の興奮、輝かしい栄誉、そして可愛い女の子とのロマンス。
    人の夢と欲望全てが息を潜めるこの場所で、少年は一人の小さな「神様」に出会った。
    「よし、ベル君、付いてくるんだ!\"ファミリア\"入団の儀式をやるぞ!」「はいっ!僕は強くなります!」
    どの\"ファミリア\"にも門前払いだった冒険者志望の少年と、構成員ゼロの真様が果たした運命の出会い。
    これは、少年が歩み、女神が記す、眷族の物語。第4回GA文庫大賞、初の大賞受賞作。"""
summ2 = """システム運用管理者必携!人気資格の公認対策書。試験合格に的を絞った解説と確認問題+模擬試験2回分(80問)"""

cur.execute(
    "INSERT INTO book_dana(user_id, title, author, publisher, status, date, url, isbn, summary) VALUES "
    "('User ID', 'ダンジョンに出会いを求めるのは間違っているだろうか', '大森藤ノ／著', 'ソフトバンククリエイティブ', '既読', '2021-06-01', 'https://cover.openbd.jp/9784797372809.jpg','978-4-7973-7280-9', ?),"
    "('User ID','ITILファンデーションシラバス2011 : ITIL資格認定試験学習書','笹森俊裕／著 満川一彦／著','翔泳社','第3章','2021-05-10','https://cover.openbd.jp/9784798125701.jpg', '978-4-7981-2570-1', ?)",
    [summ1, summ2])

# commit
con.commit()

print("生成完了\n")

# デフォルトメッセージ
default_message = "\n下記の通りに入力してください\n\n"\
                "登録 [タイトル] ([読書状態])\n"\
                "登録 [ISBNコード] ([読書状態])\n"\
                "(登録) [画像-ISBNコードが写っている]\n"\
                "表示 [ID | タイトル]\n"\
                "全て表示 (表紙)\n"\
                "削除 [ID]\n"\
                "全て削除\n"\
                "更新 [ID] [更新後の読書状態]\n\n"\
                "#()内は任意項目です\n"\
                "#[]内には実際のデータを入れて下さい\n"\
                "#各項目間はスペースを入れてください\n"\
                "#[タイトル]など各項目の中ではスペースを入れないでください\n"\
                "#[ID]は半角で入力してください\n\n"\
                "ISBNコード：978で始まるコードです\n"\
                "           裏表紙などに記載してあります"


# slackに表示
def slack_display(message, id, title, author, publisher, status, date, url, summary):
    try:
        response = client.chat_postMessage(
            channel="{}".format(message.body["channel"]),
            text="test",
            as_user=True,
            blocks=[
                {
			        "type": "header",
			        "text": {
				        "type": "plain_text",
				        "text": title
			        }
		        },
		        {
			        "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*ID　　　 :* "+id+"\n"+
                                "*著者名　 :* "+author+"\n"+
                                "*出版社　 :* "+publisher+"\n"+
                                "*読書状態 :* "+status+"\n"+
                                "*日付　　 :* "+date+"\n"+
                                "*あらすじ :*\n"+summary
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": url,
                        "alt_text": "表紙画像"
                    }
                }
            ]
        )
    except SlackApiError as e:
        assert e.response["error"] 

# 表紙画像のみ表示する
def image_only(message, title, url):
    try:
        response = client.chat_postMessage(
            channel="{}".format(message.body["channel"]),
            text="test",
            as_user=True,
            blocks=[
		        {
			        "type": "image",
                    "image_url": url,
                    "alt_text": title
                }
            ]
        )
    except SlackApiError as e:
        assert e.response["error"] 



#画像を取り込んでISBNコードを読み取る
def readerISBNList(message):
    isbn_list = []
    try:
        #画像を取り込む前準備
        img_url = message.body['files'][0]['url_private']
        flag = message.body['files'][0]['filetype']
        # 改善点(発表後) 
        # if flag == "heic" or flag == "HEIC":
        #     message.reply("申し訳ありません。「HEIC」は扱えません。\n別の画像をあげてください。") 
        #     sys.exit()
        tmpfile = "image/tmp." + flag

        rst = requests.get(img_url, headers={'Authorization': 'Bearer %s' % slack_token}, stream=True)

        #ローカルにダウンロード
        with open(tmpfile, "wb") as f: 
            shutil.copyfileobj(rst.raw, f)

        # ISBNコードの読み取り
        image = "image/tmp." + flag
        data = decode(Image.open(image))  # コードの読取り
        for i in range(len(data)):
            output = data[i][0].decode('utf-8', 'ignore')
            if re.match('^978\d',output):
                isbn_list.append(output)

        return isbn_list
    except Exception as e:
        assert e.response["error"] 



# ISBNコードによる登録
def isbnAPI(isbn):
    title,author,publisher,url,summary = "","","","",""

    book_url = 'https://api.openbd.jp/v1/get?isbn={}'.format(isbn)
    req = urllib.request.Request(book_url)
    with urllib.request.urlopen(req) as res:
        book_json = json.load(res)

    if book_json[0] is None:
        return title, author, publisher, url, summary

    title = book_json[0]['summary']['title']
    author = book_json[0]['summary']['author']
    publisher = book_json[0]['summary']['publisher']
    url = book_json[0]['summary']['cover']

    try:
        summary = book_json[0]['onix']['CollateralDetail']['TextContent'][0]['Text']
    except Exception as e:
        summary = ""
    finally:
        return title, author, publisher, url, summary



#本の登録
@respond_to(r'登録\s(.*)$')
def add(message, text):
    try:
        message.react('+1')     # リアクション　「+1」スタンプの名前
        list = text.split()     # textを分割し、リスト化

        # 各変数の初期化
        user_id = message.body['user']
        author = ""
        publisher = ""
        status = ""
        date = datetime.date.today()     # 今日の日付
        url = ""
        isbn = ""
        summary = ""

        # 画像がある場合
        if 'files' in message.body:
            default_func(message)
            return

        elif re.match('^(\d|-)+$', list[0]):      # ISBNコードによる登録
            isbn = list[0]
            title, author, publisher, url, summary = isbnAPI(isbn)

        else:
            title = list[0]

        if len(list) == 2:
            status = list[1]

        if title == "":
            message.reply("\nISBNコードから情報を取得できませんでした\n手動で登録してください\n「登録 タイトル (読書状態)」")
            return

        if url == "":
            url = default_image

        cur.execute("INSERT INTO book_dana(user_id, title, author, publisher, status, date, url, isbn, summary) VALUES (?,?,?,?,?,?,?,?,?)",
                        [user_id, title, author, publisher, status, date, url, isbn, summary])
        con.commit()    # commit
        cur.execute("SELECT LAST_INSERT_ROWID()")
        df = pd.DataFrame(cur.fetchall())
        id = df.iat[0,0]
        message.reply("ID: "+str(id)+"「"+title+"」を「"+status+"」で登録します")
    except Exception as e:
        message.reply(default_message)
    


# 指定されたIDかタイトルのデータを表示する
@respond_to(r'^表示\s(.*)$')
def display(message,text):
    message.react('+1') 
    param = text               # IDかタイトル取得
    user_id = message.body['user']
    # ID検索
    if re.match('^(\d|\s)+$', param): 
        cur.execute("SELECT * FROM book_dana WHERE id = ? AND user_id = ?",[param, user_id])
        # fetchallで直前のカーソルオブジェクトを取得し、表示
        df = pd.DataFrame(cur.fetchall())
        if df.empty:
            message.reply("ID: {}のデータはありません".format(param))
            return
        # 各要素を取得
        id = df.iat[0,0]
        title = df.iat[0,2]
        author = df.iat[0,3]
        publisher = df.iat[0,4]
        status = df.iat[0,5]
        date = df.iat[0,6]
        url = df.iat[0,7]
        summary = df.iat[0,9]
        slack_display(message, str(id), str(title), str(author), str(publisher), str(status), str(date), str(url), str(summary))

    # タイトル検索
    else:
        cur.execute("SELECT * FROM book_dana WHERE title LIKE '%"+param+"%' AND user_id = ?",[user_id])    #formatメソッドでは動かない
        df = pd.DataFrame(cur.fetchall())
        # 入力されたタイトルが見つからないとき、「本はない」と返す
        if df.empty:
            message.reply("そのようなタイトルの本はありません")
            return

        # データの表示
        for index, row in df.iterrows():
            slack_display(message, str(row[0]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[9]))



# DB全件表示
@respond_to(r'全て表示(.*)')
@respond_to(r'すべて表示(.*)')
def displayAll(message, text):
    # print(vars(message))
    user_id = message.body['user']
    param = text.strip()
    message.react('+1')     # リアクション　「+1」スタンプの名前
    cur.execute("SELECT * FROM book_dana WHERE user_id = ?",[user_id])
    df = pd.DataFrame(cur.fetchall())
    # DBにデータがない時、「何もない」と返す
    if df.empty:
        message.reply("何も登録されていません")
        return

    for index, row in df.iterrows():
        if re.match(r'表紙', param):
            image_only(message, str(row[2]), str(row[7]))
        else:
            slack_display(message, str(row[0]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[9]))
    # print(str(df))



# 指定されたIDのデータを削除する
@respond_to(r'^削除\s(.*)$')
def delete(message,text):
    message.react('+1')     # リアクション　「+1」スタンプの名前
    id = text               # ID取得
    user_id = message.body['user']
    cur.execute("SELECT * FROM book_dana WHERE id = ?",[id])
    df = pd.DataFrame(cur.fetchall())
    if df.empty:
        message.reply("ID: {}のデータはありません".format(id))
        return
    title = df.iat[0,2]
    cur.execute("DELETE FROM book_dana WHERE id = ? AND user_id = ?",[id, user_id])
    # commit
    con.commit()
    message.reply("("+id+")「"+title+"」を削除しました")



# DBの要素を全削除する
@respond_to(r'全て削除')
@respond_to(r'すべて削除')
def deleteAll(message):
    message.react('+1')     # リアクション　「+1」スタンプの名前
    user_id = message.body['user']
    cur.execute("DELETE FROM book_dana WHERE user_id = ?",[user_id])     # 全削除
    # commit
    con.commit()
    message.reply("すべて削除しました")



# 更新機能
@respond_to(r'^更新\s(.*)$')
def update(message, text):
    message.react('+1')     # リアクション　「+1」スタンプの名前
    list = text.split()
    user_id = message.body['user']
    if len(list) == 2:
        id = list[0]
        param = list[1]
        cur.execute("UPDATE book_dana SET status = ? WHERE id = ? AND user_id = ?",[param,id,user_id])
    else:
        message.reply("要素数が不正です。入力し直してください\n「更新 ID 更新後の読書状態」\n")
        return

    # commit
    con.commit()

    cur.execute("SELECT * FROM book_dana WHERE id = ? AND user_id = ?",[id,user_id])
    df = pd.DataFrame(cur.fetchall())
    # 入力されたIDがみつからない場合、ないと返す
    if df.empty:
        message.reply("ID: {}のデータはありません".format(id))
        return

    message.reply("更新しました")


@default_reply()
def default_func(message):
    if 'files' in message.body:
        # 各変数の初期化
        user_id = message.body['user']
        author = ""
        publisher = ""
        status = ""
        date = datetime.date.today()     # 今日の日付
        url = ""
        isbn_list = readerISBNList(message)
        summary = ""

        if not isbn_list:    
            message.reply("画像を読み取れませんでした")
        else:
            for isbn in isbn_list:
                title, author, publisher, url, summary = isbnAPI(isbn)

                if title == "":
                    message.reply("\nISBNコードから情報を取得できませんでした\n手動登録してください\n「登録 タイトル (読書状態)」")
                    continue

                if url == "":
                    url = default_image

                cur.execute("INSERT INTO book_dana(user_id, title, author, publisher, status, date, url, isbn, summary) VALUES (?,?,?,?,?,?,?,?,?)",
                                [user_id, title, author, publisher, status, date, url, isbn, summary])
                con.commit()    # commit
                cur.execute("SELECT LAST_INSERT_ROWID()")
                df = pd.DataFrame(cur.fetchall())
                id = df.iat[0,0]
                message.reply("ID: "+str(id)+"「"+title+"」を登録します")

    else:
        message.reply(default_message)