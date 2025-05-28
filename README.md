# 文書比較ツール

このツールは、参照文書の内容を基準として、対象文書の適合性や関連性を評価する生成AIベースのアプリケーションです。

参照文書と対象文書の間の関係性を分析し、対象文書が参照文書の基準や要件をどの程度満たしているかを評価します。様々な文書タイプや評価基準に適用可能な汎用的なフレームワークとして設計されています。

## 特徴

- 2つの文書間の関連性や適合性を分析
- 分析結果とその根拠を詳細に出力
- 複数のLLM（まずはGemini）をサポート
- 様々なファイル形式（テキスト、PDF、Office文書、画像）に対応
- CLIインターフェースを提供

## インストール

### 前提条件

- Python 3.8以上
- Gemini APIキー（または他のLLM APIキー）

### インストール手順

```bash
# リポジトリをクローン
git clone https://github.com/kzkymn/document_analyzer.git
cd document_analyzer

# 仮想環境を作成して有効化
python -m venv .venv
source .venv/bin/activate  # Linuxの場合
# または
.venv\Scripts\activate  # Windowsの場合

# 依存関係をインストール
pip install -e .
```

### 環境変数の設定

`.env.example`ファイルを`.env`にコピーして、必要な環境変数を設定します：

```bash
cp .env.example .env
# .envファイルを編集してAPIキーなどを設定
```

## 使用方法

### CLI

```bash
# 基本的な使用方法（設定ファイルは必須）
document-analyzer --source-file "参照文書のパス" --target-file "対象文書のパス" --config "設定ファイルのパス"

# `check` コマンドはデフォルトで実行されます。
# 明示的に `check` を指定することも可能です。
document-analyzer check --source-file "参照文書のパス" --target-file "対象文書のパス" --config "設定ファイルのパス"

# 出力形式を指定
document-analyzer --source-file "参照文書のパス" --target-file "対象文書のパス" --config "設定ファイルのパス" --output "出力ファイルのパス"

# 詳細ログを出力
document-analyzer --source-file "参照文書のパス" --target-file "対象文書のパス" --config "設定ファイルのパス" --verbose
```

###### オプション一覧

- `--config`, `-c` (必須): 設定ファイルのパス。
- `--source-file`, `-s` (必須): ソースファイル（比較元）のパス。
- `--target-file`, `-t` (必須): チェック対象ファイルのパス。
- `--output`, `-o`: レポート出力先パス。指定しない場合は標準出力。
- `--llm`, `-m`: 使用するLLM。デフォルトは設定ファイルの値。
- `--verbose`, `-v`: 詳細なログを出力します。
- `--extract-only`: 抽出のみを行う場合、どの項目を抽出するかを指定します (`conditions`, `facts`, `both`)。
- `--use-existing-conditions`: 既存の条件ファイルを使用し、条件の抽出処理をスキップします。
- `--use-existing-facts`: 既存のファクトファイルを使用し、ファクトの抽出処理をスキップします。
- `--conditions-output`: 抽出したチェック条件の出力先パス。デフォルトは `conditions_output.json`。
- `--facts-output`: 抽出したファクトの出力先パス。デフォルトは `facts_output.json`。
- `--yes`, `-y`: 抽出結果の確認をスキップし、常に了承します。
- `--skip-condition-extraction`: 条件の抽出処理を強制的にスキップします。
- `--skip-fact-extraction`: ファクトの抽出処理を強制的にスキップします。

##### 自律的な分析フロー

`--extract-only`, `--use-existing-conditions`, `--use-existing-facts` オプションを指定しない場合、ツールはLLMを使用してソースファイルとターゲットファイルの内容から、条件やファクトの抽出が必要かどうかを自律的に判断します。

- **ソースファイル:** ファイルの拡張子、サイズ、冒頭部分を基に、条件の抽出が必要か判断します。
- **ターゲットファイル:** ファイルの拡張子、サイズ、冒頭部分に加え、ソースファイルの内容または抽出された条件を考慮して、ファクトの抽出が必要か判断します。

LLMの判断結果に基づき、以下のいずれかの分析処理が自動的に実行されます。

- **フルペアチェック:** 条件とファクトの両方が抽出された場合。
- **条件とターゲット全文比較:** 条件のみが抽出され、ファクトが抽出されなかった場合。
- **ファクトとソース全文比較:** ファクトのみが抽出され、条件が抽出されなかった場合。
- **標準分析:** 条件もファクトも抽出されなかった場合。

この自律的な判断により、利用者は抽出に関する詳細なオプションを指定することなく、ファイルパスを指定するだけで適切な分析を実行できます。

##### 条件やファクトの抽出のみを行う

`--extract-only` オプションを使用すると、条件やファクトの抽出のみを行い、チェックを実行せずに終了できます。

```bash
# 条件のみを抽出
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --extract-only conditions

# ファクトのみを抽出
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --extract-only facts

# 条件とファクトの両方を抽出
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --extract-only both
```

##### 既存の条件やファクトファイルを使用する

`--use-existing-conditions` や `--use-existing-facts` オプションを使用すると、既存の条件やファクトファイルを使用してチェックを実行できます。また、ファイルが存在する場合は自動的に使用されます。

```bash
# 既存の条件ファイルを使用して分析を実行
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --use-existing-conditions

# 既存のファクトファイルを使用して分析を実行
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --use-existing-facts
```

##### 条件やファクトファイルを編集した後の再度チェック

条件やファクトを抽出した後にファイルを編集した場合、以下の方法で再度チェックを実行できます：

```bash
# 条件ファイルを編集した後に再度チェックを実行
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --use-existing-conditions

# ファクトファイルを編集した後に再度チェックを実行
document-analyzer --source-file "条件ファイルのパス" --target-file "ファクトファイルのパス" --config "設定ファイルのパス" --use-existing-facts
```


## 設定

### 設定ファイル

設定ファイルはYAML形式で、以下のような構造を持ちます：

```yaml
# プロンプト設定
prompt:
  template_path: "prompt.txt"  # プロンプトテンプレートのパス（相対パスまたは絶対パス）
  description: "週次レポートチェック"  # 説明（オプション）
```

設定ファイルのパスは、`--config`オプションで指定する必要があります。相対パスの場合は、カレントディレクトリからの相対パスとして解釈されます。

### プロンプトテンプレート

プロンプトテンプレートは、LLMに送信するプロンプトの内容を定義するテキストファイルです。テンプレート内では、以下の変数を使用できます：

- `{reference_text}`: 参照文書の内容
- `{file_content}`: 分析対象文書の内容

### サンプル設定

サンプル設定ファイルとプロンプトテンプレートは以下の場所にあります：

- サンプル実装例: `sample_input/weekly_report_check/config.yaml` と `sample_input/weekly_report_check/prompt.txt`

これらのサンプルを参考に、独自の設定ファイルとプロンプトテンプレートを作成できます。

### プロンプトファイル

アプリケーションは`config/prompts`ディレクトリに以下のプロンプトファイルを持っています：

- `default_analysis_prompt.txt`: 文書分析の基本プロンプト
- `pair_check_prompt.txt`: 条件とファクトのペアチェック用プロンプト
- `should_extract_prompt.txt`: 抽出要否判断用プロンプト
- `condition_extraction_prompt.txt`: 条件抽出用プロンプト
- `fact_extraction_prompt.txt`: ファクト抽出用プロンプト

各プロンプトファイルの役割：

1. **default_analysis_prompt.txt**
   - 文書全体の分析を行うためのプロンプト
   - 変数: `{reference_text}`, `{file_content}`

2. **pair_check_prompt.txt**
   - 条件とファクトのペアが適合しているかを判断するプロンプト
   - 変数: `{condition}`, `{fact}`

3. **should_extract_prompt.txt**
   - ファイルから条件やファクトを抽出する必要があるかを判断するプロンプト
   - 変数: `{file_path}`, `{file_size}`, `{file_head}`, `{source_context}`

4. **condition_extraction_prompt.txt**
   - テキストから条件を抽出するためのプロンプト
   - 変数: `{text}`, `{structure_summary}`

5. **fact_extraction_prompt.txt**
   - テキストからファクトを抽出するためのプロンプト
   - 変数: `{text}`, `{structure_summary}`

#### プロンプトのカスタマイズ

プロンプトファイルは、アプリケーションの動作を調整するために編集できます。各プロンプトファイルには、LLMへの指示と出力形式が定義されています。

プロンプトをカスタマイズする際の注意点：

1. 変数プレースホルダー（`{variable_name}`形式）は変更しないでください
2. 出力形式の構造は維持してください（特にJSONフォーマットを使用するプロンプト）
3. 指示の内容は調整できますが、基本的な機能（条件抽出、ファクト抽出など）を変更しないようにしてください

例えば、条件抽出プロンプト（`condition_extraction_prompt.txt`）を編集して、特定の種類の条件に焦点を当てるように調整できます：

```markdown
# 指示
1. テキストから**セキュリティ関連**のチェック条件を抽出してください。
2. 条件は、その意味が明確に伝わるように適切な粒度で抽出してください。
...
```

プロンプトファイルを編集したのち、再度コマンドを実行するときから新しいプロンプトが使用されます。

##### プロンプト編集が必要になる想定ケース

以下のような場合にプロンプトの編集が有効です：

1. **抽出粒度の調整**
   - **条件抽出の粒度が細かすぎる場合**: 複数の小さな条件が別々に抽出され、本来は一つの大きな条件として扱うべき場合

   ```markdown
   # 指示
   2. 条件は、その意味が明確に伝わるように適切な粒度で抽出してください。
      - 条件が複数の関連する要素を含む場合は、必ずそれらをまとめて1つの条件として抽出してください。
      - **関連する複数の条件は可能な限り統合し、より大きな単位で抽出してください。**
   ```

   - **条件抽出の粒度が粗すぎる場合**: 一つの大きな条件に複数の独立した要件が含まれている場合

   ```markdown
   # 指示
   2. 条件は、その意味が明確に伝わるように適切な粒度で抽出してください。
      - **独立した要件は別々の条件として抽出してください。一つの条件に複数の独立した要件を含めないでください。**
      - 条件の意味を理解するために必要な文脈も含めてください。
   ```

   - **ファクト抽出の粒度調整**: ファクトが細かすぎるまたは粗すぎる場合も同様に調整可能

2. **特定の種類の条件やファクトに焦点を当てる**
   - 特定の分野（セキュリティ、パフォーマンス、コンプライアンスなど）に関連する条件のみを抽出

   ```markdown
   # 指示
   1. テキストから**セキュリティ関連**のチェック条件を抽出してください。
   ```

3. **階層構造の扱いの調整**
   - 親子関係の判定基準を厳しくしたい場合

   ```markdown
   # 指示
   5. 条件の階層構造や関連性が明確な場合は、親子関係を表現してください。
      - **親子関係は、明示的に「〜の詳細として」「〜の一部として」などの表現がある場合のみ設定してください。**
   ```

4. **出力の詳細度の調整**
   - より詳細な説明や根拠を含めたい場合

   ```markdown
   # 出力形式
   JSONフォーマットで出力してください。以下の構造に従ってください：

   [
     {
       "id": 1,
       "text": "条件1のテキスト",
       "parent_id": null,
       "source": "条件が記載されている章や節",
       "importance": "high/medium/low"
     },
     ...
   ]
   ```

プロンプトファイルを編集したのち、再度コマンドを実行するときから新しいプロンプトが使用されます。

### 設定の優先順位

設定は以下の優先順位で読み込まれます：

1. コマンドライン引数
2. 環境変数
3. 設定ファイル（`--config`オプションで指定）

### ログレベル

ログレベルは以下の方法で制御できます：

- `--verbose` フラグを使用: デバッグレベルのログが出力されます
- 環境変数 `LOG_LEVEL` を設定: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` のいずれかを指定
- デフォルトのログレベルは `INFO` です

### 終了コード

CLIの `check` コマンドは、分析結果に応じて以下の終了コードを返します：

- `0`: 適合（COMPLIANT）
- `1`: 不適合（NON_COMPLIANT）
- `2`: 無関係（UNRELATED）
- `3`: 不明（UNKNOWN）
- `-1`: エラー発生

## トラブルシューティング

### 設定ファイルが見つからない場合

設定ファイルが見つからない場合は、以下を確認してください：

1. 指定したパスが正しいか
2. ファイルが実際に存在するか
3. ファイルの読み取り権限があるか

- 例：

    ```text
    document-analyzer -s <参照文書のパス> -t <対象文書のパス> -c <設定ファイルのパス>
    ```
    
    - 具体例:
    
        ```text
        document-analyzer -s sample_input/weekly_report_check/writing_guidelines.txt -t sample_input/weekly_report_check/compliant_report.txt -c sample_input/weekly_report_check/config.yaml
        ```

### プロンプトテンプレートが見つからない場合

プロンプトテンプレートが見つからない場合は、設定ファイル内の`prompt.template_path`が正しいパスを指しているか確認してください。相対パスの場合は、設定ファイルのディレクトリからの相対パスとして解釈されます。

## 開発

### 開発用依存関係のインストール

```bash
pip install -e ".[dev]"
```

### テストの実行

```bash
pytest
# カバレッジレポート付きでテストを実行
pytest --cov=document_analyzer
```

### LLMプロセッサーの拡張

現在のバージョンでは、Gemini APIのみがサポートされています。新しいLLMプロセッサーを追加するには：

1. `document_analyzer/llm/` ディレクトリに新しいプロセッサークラスを作成
2. `LLMProcessor` 基底クラスを継承
3. `TextComparisonAnalyzer.register_processor()` メソッドを使用して登録

```python
from document_analyzer.core.analyzer import TextComparisonAnalyzer
from document_analyzer.llm.your_new_processor import YourNewProcessor

TextComparisonAnalyzer.register_processor("your_llm_name", YourNewProcessor)
```

### ファイルフォーマット対応状況

現在のバージョンでは、主にテキストファイルの処理に対応しています。README に記載されている「PDF、Office文書、画像」への対応は将来の拡張として計画されていますが、現時点では実装されていません。これらのファイル形式を処理するには、`document_analyzer/file_processors/` ディレクトリに適切なプロセッサーを実装する必要があります。

## ライセンス

MIT
