"""
APIインターフェースモジュール。
FastAPIベースのREST APIを提供する。
"""

import os
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .core.analyzer import TextComparisonAnalyzer
from .core.extractor import TextExtractor  # TextExtractor をインポート
from .core.pair_check import (  # PairCheckItemType をインポート
    PairCheckItem,
    PairCheckItemType,
)
from .core.processor import ComplianceStatus, Evidence, Recommendation
from .utils.config import config
from .utils.logging import logger

# FastAPIアプリケーションを作成
app = FastAPI(
    title="文書分析ツールAPI",
    description="テキスト間の関連性や適合性を分析するAPI",
    version="0.1.0",
)

# CORSミドルウェアを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 一時ファイル保存用ディレクトリ
TEMP_DIR = Path("./temp")
TEMP_DIR.mkdir(exist_ok=True)


class ComplianceStatusEnum(str, Enum):
    """適合状態を表す列挙型（API用）"""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNRELATED = "unrelated"
    UNKNOWN = "unknown"


class EvidenceModel(BaseModel):
    """根拠を表すデータモデル（API用）"""

    text: str
    source: Optional[str] = None
    relevance: Optional[float] = None


class RecommendationModel(BaseModel):
    """推奨事項を表すデータモデル（API用）"""

    text: str
    priority: Optional[int] = None


class AnalysisResultModel(BaseModel):
    """分析結果を表すデータモデル（API用）"""

    status: ComplianceStatusEnum
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    summary: str
    evidence: List[EvidenceModel]
    recommendations: List[RecommendationModel]


class AnalysisRequest(BaseModel):
    """分析リクエストを表すデータモデル"""

    source_text: str
    llm: Optional[str] = None


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "文書分析ツールAPI",
        "version": "0.1.0",
        "endpoints": [
            "/api/check",
            "/api/processors",
            "/api/extract",
            "/api/check/with_existing",  # 新しいエンドポイントを追加
        ],
    }


@app.get("/api/processors")
async def get_processors():
    """利用可能なLLMプロセッサーを取得する"""
    return {
        "processors": TextComparisonAnalyzer.get_available_processors(),
        "default": config.get("llm.default", "gemini"),
    }


@app.post("/api/check", response_model=AnalysisResultModel)
async def check_compliance(
    source_text: str = Form(...),
    target_file: UploadFile = File(...),
    llm: Optional[str] = Form(None),
):
    """
    文書分析を実行する

    - **source_text**: ソーステキスト
    - **target_file**: 分析対象ファイル
    - **llm**: 使用するLLM（オプション）
    """
    logger.info(f"APIリクエスト受信: {target_file.filename}")

    try:
        # 一時ファイルを作成して保存
        suffix = Path(target_file.filename).suffix
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as temp_file:
            temp_file_path = temp_file.name
            content = await target_file.read()
            temp_file.write(content)

        # 分析器を初期化
        analyzer = TextComparisonAnalyzer(llm_name=llm)

        # 分析を実行
        result = analyzer.analyze(source_text, temp_file_path)

        # 一時ファイルを削除
        os.unlink(temp_file_path)

        # 結果をAPIモデルに変換
        api_result = AnalysisResultModel(
            status=ComplianceStatusEnum(result.status.value),
            confidence_score=result.confidence_score,
            summary=result.summary,
            evidence=[
                EvidenceModel(text=e.text, source=e.source, relevance=e.relevance)
                for e in result.evidence
            ],
            recommendations=[
                RecommendationModel(text=r.text, priority=r.priority)
                for r in result.recommendations
            ],
        )

        logger.info(f"分析完了: {target_file.filename}, 状態: {result.status.value}")
        return api_result

    except Exception as e:
        logger.error(f"APIエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/check/report")
async def check_compliance_with_report(
    source_text: str = Form(...),
    target_file: UploadFile = File(...),
    llm: Optional[str] = Form(None),
):
    """
    文書分析を実行し、Markdownレポートを返す

    - **source_text**: ソーステキスト
    - **target_file**: 分析対象ファイル
    - **llm**: 使用するLLM（オプション）
    """
    logger.info(f"レポートAPIリクエスト受信: {target_file.filename}")

    try:
        # 一時ファイルを作成して保存
        suffix = Path(target_file.filename).suffix
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as temp_file:
            temp_file_path = temp_file.name
            content = await target_file.read()
            temp_file.write(content)

        # レポート出力用の一時ファイル
        report_path = TEMP_DIR / f"report_{Path(target_file.filename).stem}.md"

        # 分析器を初期化
        analyzer = TextComparisonAnalyzer(llm_name=llm)

        # 分析を実行
        result = analyzer.analyze(source_text, temp_file_path, report_path)

        # 一時ファイルを削除
        os.unlink(temp_file_path)

        logger.info(f"レポート生成完了: {report_path}")

        # レポートファイルを返す
        return FileResponse(
            path=report_path,
            media_type="text/markdown",
            filename=f"analysis_report_{Path(target_file.filename).stem}.md",
        )

    except Exception as e:
        logger.error(f"APIエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 抽出対象を表す列挙型
class ExtractionTargetEnum(str, Enum):
    """抽出対象を表す列挙型（API用）"""

    CONDITIONS = "conditions"
    FACTS = "facts"
    BOTH = "both"


# 抽出結果を表すデータモデル
class ExtractionResultModel(BaseModel):
    """抽出結果を表すデータモデル（API用）"""

    conditions: Optional[List[EvidenceModel]] = None
    facts: Optional[List[EvidenceModel]] = None


@app.post("/api/extract", response_model=ExtractionResultModel)
async def extract_items(
    target_file: UploadFile = File(...),
    target: ExtractionTargetEnum = Form(ExtractionTargetEnum.BOTH),
    source_text: Optional[str] = Form(None),  # ファクト抽出時のソースコンテキスト用
    llm: Optional[str] = Form(None),
):
    """
    ファイルから条件またはファクトを抽出する

    - **target_file**: 抽出対象ファイル
    - **target**: 抽出対象（conditions, facts, both）
    - **source_text**: ファクト抽出時のソースコンテキスト（オプション）
    - **llm**: 使用するLLM（オプション）
    """
    logger.info(f"抽出APIリクエスト受信: {target_file.filename}, 対象: {target}")

    try:
        # 一時ファイルを作成して保存
        suffix = Path(target_file.filename).suffix
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as temp_file:
            temp_file_path = temp_file.name
            content = await target_file.read()
            temp_file.write(content)

        from .core.analyzer import (
            TextComparisonAnalyzer,
        )  # TextExtractor初期化のために必要
        from .core.extractor import TextExtractor

        # TextExtractor初期化のためにダミーのanalyzerを生成 (processorを取得するため)
        # TODO: TextExtractorがprocessorを直接受け取るようにリファクタリングする方が良いかもしれない
        analyzer = TextComparisonAnalyzer(llm_name=llm)
        extractor = TextExtractor(analyzer.processor)

        conditions = None
        facts = None

        if target in [ExtractionTargetEnum.CONDITIONS, ExtractionTargetEnum.BOTH]:
            logger.info("条件を抽出します。")
            # 抽出要否判断はCLI側で行うため、APIでは常に抽出を試みる
            extracted_conditions = extractor.extract_items(temp_file_path, "conditions")
            conditions = [
                EvidenceModel(
                    text=c.text,
                    source=c.source,
                    relevance=None,  # APIではrelevanceは使用しない
                )
                for c in extracted_conditions
            ]
            logger.info(f"条件抽出完了: {len(conditions)}個")

        if target in [ExtractionTargetEnum.FACTS, ExtractionTargetEnum.BOTH]:
            logger.info("ファクトを抽出します。")
            # 抽出要否判断はCLI側で行うため、APIでは常に抽出を試みる
            extracted_facts = extractor.extract_items(
                temp_file_path, "facts", source_context=source_text
            )
            facts = [
                EvidenceModel(
                    text=f.text,
                    source=f.source,
                    relevance=None,  # APIではrelevanceは使用しない
                )
                for f in extracted_facts
            ]
            logger.info(f"ファクト抽出完了: {len(facts)}個")

        # 一時ファイルを削除
        os.unlink(temp_file_path)

        return ExtractionResultModel(conditions=conditions, facts=facts)

    except Exception as e:
        logger.error(f"抽出APIエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/check/with_existing", response_model=None)
async def check_compliance_with_existing(
    conditions_file: UploadFile = File(...),
    facts_file: UploadFile = File(...),
    output_report: Optional[bool] = Form(False),  # レポート出力フラグ
    llm: Optional[str] = Form(None),
):
    """
    既存の条件ファイルとファクトファイルを使用して文書分析を実行する

    - **conditions_file**: 条件を含むJSONファイル
    - **facts_file**: ファクトを含むJSONファイル
    - **output_report**: 結果をMarkdownレポートとして返すか (デフォルト: False)
    - **llm**: 使用するLLM（オプション）
    """
    logger.info(
        f"既存ファイル分析APIリクエスト受信: 条件ファイル={conditions_file.filename}, ファクトファイル={facts_file.filename}, レポート出力={output_report}"
    )

    try:
        # 一時ファイルを作成して保存 (条件ファイル)
        conditions_suffix = Path(conditions_file.filename).suffix
        with NamedTemporaryFile(
            delete=False, suffix=conditions_suffix, dir=TEMP_DIR
        ) as temp_conditions_file:
            temp_conditions_path = temp_conditions_file.name
            conditions_content = await conditions_file.read()
            temp_conditions_file.write(conditions_content)

        # 一時ファイルを作成して保存 (ファクトファイル)
        facts_suffix = Path(facts_file.filename).suffix
        with NamedTemporaryFile(
            delete=False, suffix=facts_suffix, dir=TEMP_DIR
        ) as temp_facts_file:
            temp_facts_path = temp_facts_file.name
            facts_content = await facts_file.read()
            temp_facts_file.write(facts_content)

        # TextExtractorを初期化して条件とファクトを読み込む
        # TextExtractor初期化のためにダミーのanalyzerを生成 (processorを取得するため)
        analyzer_for_load = TextComparisonAnalyzer(llm_name=llm)
        extractor = TextExtractor(analyzer_for_load.processor)

        conditions = extractor.load_items_from_file(
            temp_conditions_path, PairCheckItemType.CONDITION
        )
        facts = extractor.load_items_from_file(temp_facts_path, PairCheckItemType.FACT)

        # 一時ファイルを削除
        os.unlink(temp_conditions_path)
        os.unlink(temp_facts_path)

        # 分析器を初期化
        analyzer = TextComparisonAnalyzer(llm_name=llm)

        # 分析を実行 (PairCheckItemのリストを渡す)
        # CLIの run_pair_check 関数に相当するロジックをここに実装
        from .core.pair_check import PairChecker
        from .core.report import (
            AnalysisReportGenerator,
        )  # レポート生成のためにインポート

        pair_checker = PairChecker(analyzer.processor)
        pair_check_result = pair_checker.check_pairs(conditions, facts)

        # PairCheckResult を AnalysisResult に変換してレポート生成に渡す
        # TODO: PairCheckResult と AnalysisResult の構造を整理し、共通化または変換を容易にする
        # 現状は PairCheckResult から AnalysisResult に必要な情報をマッピングする
        # ここでは簡易的に PairCheckResult の情報を AnalysisResult に詰める
        # 正確なマッピングは PairCheckResult の構造に依存する
        # 仮のマッピングとして、overall_status を status に、summary を生成するなど
        # evidence と recommendations は PairCheckResult の詳細から構築する必要がある
        # ここでは詳細な変換ロジックは省略し、AnalysisResultModel の構造に合うように仮のデータを設定
        # 実際のPairCheckResultの構造に合わせて修正が必要
        # 例:
        # status = ComplianceStatusEnum(pair_check_result.overall_status.value)
        # confidence_score = pair_check_result.overall_confidence # 仮
        # summary = "Pair check analysis completed." # 仮
        # evidence = [] # PairCheckResult の詳細から構築
        # recommendations = [] # PairCheckResult の詳細から構築

        # 簡易的な AnalysisResultModel の生成 (PairCheckResult の詳細を反映させるには PairCheckResult の構造確認が必要)
        # ここでは PairCheckResult の overall_status のみを反映させる
        analysis_result_for_report = type(
            "AnalysisResult",
            (object,),
            {
                "status": pair_check_result.overall_status,
                "confidence_score": 1.0,  # 仮の値
                "summary": "Pair check analysis completed.",  # 仮の値
                "evidence": [],  # 仮の値
                "recommendations": [],  # 仮の値
            },
        )()

        if output_report:
            # レポートを生成してファイルとして返す
            report_generator = AnalysisReportGenerator(analyzer.processor)
            # レポート生成には元のファイル名が必要だが、ここではファイルパスしかないので仮の名前を使用
            # TODO: 元のファイル名をリクエストで受け取るか、一時ファイル名から推測する
            source_filename = Path(conditions_file.filename).stem
            target_filename = Path(facts_file.filename).stem
            report_content = report_generator.generate_report(
                analysis_result_for_report,  # PairCheckResult を変換した AnalysisResult オブジェクト
                f"{source_filename}_conditions.json",  # 仮のファイル名
                f"{target_filename}_facts.json",  # 仮のファイル名
            )

            report_path = (
                TEMP_DIR / f"pair_check_report_{source_filename}_{target_filename}.md"
            )
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            logger.info(f"ペアチェックレポート生成完了: {report_path}")

            return FileResponse(
                path=report_path,
                media_type="text/markdown",
                filename=f"pair_check_report_{source_filename}_{target_filename}.md",
            )
        else:
            # 結果をAPIモデルに変換してJSONで返す
            # PairCheckResult を AnalysisResultModel に変換するロジックが必要
            # ここでは PairCheckResult の overall_status のみをマッピング
            api_result = AnalysisResultModel(
                status=ComplianceStatusEnum(pair_check_result.overall_status.value),
                confidence_score=1.0,  # 仮の値
                summary="Pair check analysis completed.",  # 仮の値
                evidence=[],  # PairCheckResult の詳細から構築が必要
                recommendations=[],  # PairCheckResult の詳細から構築が必要
            )
            logger.info(
                f"ペアチェック分析完了: 状態: {pair_check_result.overall_status.value}"
            )
            return api_result

    except Exception as e:
        logger.error(f"既存ファイル分析APIエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
