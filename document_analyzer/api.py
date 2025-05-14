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
from .core.processor import ComplianceStatus, Evidence, Recommendation
from .utils.config import config
from .utils.logging import logger


# FastAPIアプリケーションを作成
app = FastAPI(
    title="文書分析ツールAPI",
    description="テキスト間の関連性や適合性を分析するAPI",
    version="0.1.0"
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
            "/api/processors"
        ]
    }


@app.get("/api/processors")
async def get_processors():
    """利用可能なLLMプロセッサーを取得する"""
    return {
        "processors": TextComparisonAnalyzer.get_available_processors(),
        "default": config.get("llm.default", "gemini")
    }


@app.post("/api/check", response_model=AnalysisResultModel)
async def check_compliance(
    source_text: str = Form(...),
    target_file: UploadFile = File(...),
    llm: Optional[str] = Form(None)
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
                EvidenceModel(
                    text=e.text,
                    source=e.source,
                    relevance=e.relevance
                ) for e in result.evidence
            ],
            recommendations=[
                RecommendationModel(
                    text=r.text,
                    priority=r.priority
                ) for r in result.recommendations
            ]
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
    llm: Optional[str] = Form(None)
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
            filename=f"analysis_report_{Path(target_file.filename).stem}.md"
        )
    
    except Exception as e:
        logger.error(f"APIエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))