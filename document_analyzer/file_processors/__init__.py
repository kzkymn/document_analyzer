"""
ファイルプロセッサーパッケージ。

様々なファイル形式からテキストコンテンツを抽出するためのプロセッサーを含みます。
各プロセッサーは特定のファイルタイプ（例: PDF, Office文書, 画像）の処理を担当します。

現在の実装状況:
- pdf_processor.py: PDFファイル処理のプレースホルダー
- office_processor.py: Office文書処理のプレースホルダー
- image_processor.py: 画像ファイル処理のプレースホルダー

これらのプロセッサーは、対応するライブラリをインストールし、processメソッドに
実際の抽出ロジックを実装することで機能します。
"""

# TODO: 必要に応じて、ここで各プロセッサーモジュールをインポートし、
# 外部からアクセス可能なリストや辞書として公開することも検討できます。
# 例:
# from .pdf_processor import PdfProcessor
# from .office_processor import OfficeProcessor
# from .image_processor import ImageProcessor
#
# AVAILABLE_PROCESSORS = {
#     "pdf": PdfProcessor,
#     "office": OfficeProcessor,
#     "image": ImageProcessor,
#     # 他のプロセッサーもここに追加
# }
