
# Gemini API: ファイル検索機能 完全ガイド

Gemini APIの強力な機能である「ファイル検索」を利用することで、RAG（Retrieval-Augmented Generation）を簡単に実装できます。この機能は、ユーザーが提供したファイル群から関連情報を自動的に検索し、それをコンテキストとしてモデルに渡すことで、より正確で根拠のある回答を生成します。

このドキュメントでは、ファイル検索機能の概要と、Pythonを使った具体的な実装方法をデモコードと共に解説します。

## 主な特徴

- **セマンティック検索**: キーワードだけでなく、文章の意味を理解して関連性の高い情報を検索します。
- **自動処理**: ファイルのアップロード、チャンク化、インデックス登録をAPIが自動で行います。
- **永続的なデータストア**: `FileSearchStore`を作成することで、インデックス化されたデータを永続的に保存し、複数のAPIコールで再利用できます。
- **メタデータフィルタリング**: 各ファイルにカスタムメタデータを付与し、検索対象を動的に絞り込めます。
- **引用（Citation）**: モデルの回答がどのドキュメントのどの部分に基づいているかを明確に示し、ファクトチェックを容易にします。

---

## セットアップ

アプリケーションを実行するために、まずは環境をセットアップします。
`uv` を使用して、依存関係をインストールします。

### 1. ライブラリのインストール

以下のコマンドで必要なライブラリをインストールします。

```bash
uv pip install -r src/requirements.txt
```

### 2. APIキーの設定

Gemini APIを利用するにはAPIキーが必要です。`src/.env` ファイルを作成し、以下の内容を記載してください。

```bash
GEMINI_API_KEY=your_api_key_here
```

APIキーは [Google AI Studio](https://makersuite.google.com/app/apikey) から取得できます。

---

## アプリケーション解説

`src/app.py`は、StreamlitベースのPDFチャットアプリケーションで、ファイル検索APIを活用しています。以下、実装の主要な部分をステップごとに解説します。

### ステップ1: ファイル検索ストアの作成

PDFがアップロードされると、検索対象となるファイルを格納するための`FileSearchStore`を作成します。ストアには、ユニークなIDを含む表示名を付けます。

```python
# src/app.py - create_file_search_store()

def create_file_search_store(store_name, lang='en'):
    """Create a new File Search Store"""
    try:
        store = client.file_search_stores.create(
            config={'display_name': store_name}
        )
        return store
    except Exception as e:
        st.error(get_text('error_create_store', lang).format(e))
        return None
```

アプリ内では、ユーザーがPDFをアップロードした際に以下のように呼び出されます：

```python
unique_id = generate_random_id()
store_display_name = f'pdf-chat-store-{unique_id}'
store = create_file_search_store(store_display_name, lang)
```

### ステップ2: PDFファイルのアップロードとインポート

アップロードされたPDFファイルを一時保存してから、`FileSearchStore`にアップロードします。カスタムメタデータとして、ソースとタイムスタンプを付与します。

```python
# src/app.py - upload_file_to_store()

def upload_file_to_store(file_path, store_name, display_name, lang='en'):
    """Upload file to File Search Store"""
    try:
        upload_op = client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store_name,
            config={
                'display_name': display_name,
                'custom_metadata': [
                    {"key": "source", "string_value": "streamlit_upload"},
                    {"key": "timestamp", "numeric_value": int(time.time())}
                ]
            }
        )
        upload_op = wait_operation(client, upload_op)
        return upload_op.response
    except Exception as e:
        st.error(get_text('error_upload_store', lang).format(e))
        return None
```

`wait_operation()`関数を使用して、アップロード処理の完了を待機します：

```python
def wait_operation(client, op, sleep_sec=2, max_wait_sec=300):
    """Wait for Operations API to complete with timeout"""
    start = time.time()
    while not op.done:
        if time.time() - start > max_wait_sec:
            raise TimeoutError("Operation timed out.")
        time.sleep(sleep_sec)
        op = client.operations.get(op)
    return op
```

### ステップ3: ファイル内容に関する質問

PDFがインデックス化されたら、その内容について質問できます。`generate_content`を呼び出す際に、`config`パラメータで作成した`FileSearchStore`を指定します。選択されたモデルを使用して回答を生成します。

```python
# src/app.py - query_file_search()

def query_file_search(question, store_name, model, lang='en'):
    """Query the File Search Store with a question"""
    try:
        response = client.models.generate_content(
            model=model,
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            )
        )
        return response
    except Exception as e:
        st.error(get_text('error_query', lang).format(e))
        return None
```

使用するモデルはサイドバーで選択できます（デフォルト: gemini-2.5-flash）。

### ステップ4: 引用（Grounding Metadata）の表示

回答の信頼性を確認するために、どの情報を参照したかを示す引用情報を表示します。Streamlitのexpanderを使用して、ソース情報を確認できるようにしています。

```python
# src/app.py - チャットインターフェース内

try:
    gm = response.candidates[0].grounding_metadata
    if gm:
        with st.expander(get_text('view_sources', lang)):
            st.json(str(gm))
except:
    pass
```

### ステップ5: 多言語対応とモデル選択

アプリケーションは英語と日本語のUIに対応しており、サイドバーで言語とモデルを選択できます。

```python
# src/app.py - 言語とモデル選択

# 言語選択
lang_options = {'English': 'en', '日本語': 'ja'}
selected_lang = st.selectbox(
    get_text('language', lang),
    options=list(lang_options.keys()),
    index=0 if lang == 'en' else 1
)

# モデル選択
model_options = [
    'gemini-2.5-flash',
    'gemini-2.5-pro'
]
selected_model = st.selectbox(
    get_text('model', lang),
    options=model_options,
    index=model_options.index(st.session_state.model)
)
```

翻訳は辞書ベースで管理され、`get_text(key, lang)`関数を通じてすべてのUIテキストが多言語対応されています。

### ステップ6: クリーンアップ

ユーザーがPDFをクリアするか、新しいPDFをアップロードする際に、作成した`FileSearchStore`を削除してリソースを解放します。

```python
# src/app.py - cleanup_store()

def cleanup_store(store_name, lang='en'):
    """Delete the File Search Store"""
    try:
        client.file_search_stores.delete(
            name=store_name,
            config={'force': True}
        )
        return True
    except Exception as e:
        st.error(get_text('error_cleanup', lang).format(e))
        return False
```

---

## アプリケーションの実行

すべての準備が整いました。以下のコマンドを実行して、Streamlitアプリケーションを起動しましょう。

```bash
uv run streamlit run src/app.py
```

ブラウザが自動的に開き、アプリケーションが `http://localhost:8501` で起動します。

### 使い方

1. サイドバーから言語を選択（English / 日本語）
2. 使用するGemini AIモデルを選択
3. PDFファイルをアップロード
4. 画面下部のチャット入力欄にPDFに関する質問を入力
5. Gemini AIが回答を生成
6. 「📚 ソースを表示」で出典を確認

---
## 実装情報

### 対応モデル
- gemini-2.5-flash (デフォルト)
- gemini-2.5-pro

### ファイル形式
- PDF (.pdf)

### 依存ライブラリ
- streamlit
- google-generativeai
- PyPDF2
- python-dotenv

### 言語対応
- 英語 (English)
- 日本語
