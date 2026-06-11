from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "docs" / "project_overview.pdf"


class Divider(Flowable):
    def __init__(self, color: colors.Color = colors.HexColor("#087F8C"), width: float = 1.4):
        super().__init__()
        self.color = color
        self.width = width

    def wrap(self, available_width, available_height):
        self.available_width = available_width
        return available_width, 10

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.width)
        self.canv.line(0, 4, self.available_width, 4)


def bullets(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=10) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
        bulletFontName="Helvetica",
        bulletFontSize=8,
        bulletColor=colors.HexColor("#087F8C"),
    )


def section(title: str, story: list, text: str | None = None) -> None:
    story.append(Paragraph(title, STYLES["SectionTitle"]))
    story.append(Divider())
    if text:
        story.append(Paragraph(text, STYLES["Body"]))
        story.append(Spacer(1, 8))


def pipeline_table() -> Table:
    rows = [
        ["1", "Ingest", "Product Hunt launches and selected company websites are collected."],
        ["2", "Normalize", "Records become a shared StartupEvidence model."],
        ["3", "Chunk", "Evidence is converted into source-aware chunks with metadata."],
        ["4", "Embed", "Gemini embeddings convert chunks into dense semantic vectors."],
        ["5", "Store", "Pinecone stores vectors and metadata for retrieval."],
        ["6", "Retrieve", "The user query is embedded and sent to Pinecone."],
        ["7", "Rerank", "Semantic relevance and trend signals reorder the evidence."],
        ["8", "Generate", "Gemini receives cited context and returns an evidence-backed answer."],
    ]
    table = Table([["Step", "Stage", "What Happens"], *rows], colWidths=[0.55 * inch, 1.2 * inch, 4.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17202A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F3F8F8")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def source_table() -> Table:
    rows = [
        ["Product Hunt API", "Live launch freshness, topics, votes, comments, descriptions, URLs."],
        ["Company websites", "Richer product positioning and feature context from selected homepages."],
        ["Demo sample data", "Offline fallback for testing and demonstrations without external services."],
    ]
    table = Table([["Source", "Role In The Project"], *rows], colWidths=[1.75 * inch, 4.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3546A6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5E6874"))
    canvas.drawString(doc.leftMargin, 0.45 * inch, "Global Startup Radar - High-Level Project Overview")
    canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf() -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.68 * inch,
        title="Global Startup Radar Project Overview",
        author="Ravi Kiran Uppalapati",
        subject="High-level overview of a Streamlit, Gemini, Pinecone, and LangChain RAG project",
    )

    story = []
    story.append(Spacer(1, 0.55 * inch))
    story.append(Paragraph("Global Startup Radar", STYLES["CoverTitle"]))
    story.append(Paragraph("High-Level Project Overview", STYLES["CoverSubtitle"]))
    story.append(Spacer(1, 0.22 * inch))
    story.append(Divider(colors.HexColor("#C65A3A"), 2.4))
    story.append(Spacer(1, 0.22 * inch))
    story.append(
        Paragraph(
            "A live RAG application for discovering emerging startups using Product Hunt, company websites, "
            "Gemini embeddings, Pinecone retrieval, explainable reranking, and Gemini answer generation.",
            STYLES["Lead"],
        )
    )
    story.append(Spacer(1, 0.35 * inch))
    cover_items = [
        ["Project type", "Streamlit dashboard + RAG pipeline"],
        ["Core stack", "LangChain, Gemini, Pinecone, Product Hunt API"],
        ["Primary output", "Cited startup trend answers with transparent RAG trace"],
        ["Audience", "Project reviewers, builders, analysts, and startup-curious users"],
    ]
    cover_table = Table(cover_items, colWidths=[1.35 * inch, 4.9 * inch])
    cover_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#17202A")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F7F9FC")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE8")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(cover_table)
    story.append(PageBreak())

    section(
        "1. Executive Summary",
        story,
        "Global Startup Radar helps users explore emerging startups around the world. The app starts with "
        "live launch evidence, turns that evidence into searchable vectors, retrieves the most relevant chunks "
        "for each question, reranks them with transparent trend signals, and asks Gemini to generate a cited answer.",
    )
    story.append(
        Paragraph(
            "The submission is intentionally transparent: reviewers can inspect the chunks, embedding/retrieval "
            "settings, Pinecone output before reranking, final reranked order, and the exact LLM prompt.",
            STYLES["Body"],
        )
    )
    story.append(Spacer(1, 8))

    section("2. Problem And User Need", story)
    story.append(
        bullets(
            [
                "Startup discovery is noisy: signals are scattered across launch platforms, websites, and news.",
                "Simple keyword search misses semantically similar products and themes.",
                "LLM answers can sound confident unless grounded in retrieved evidence.",
                "Reviewers need to see how the RAG pipeline works, not only the final answer.",
            ],
            STYLES["Body"],
        )
    )
    story.append(Spacer(1, 8))

    section("3. Data Sources", story)
    story.append(source_table())
    story.append(Spacer(1, 12))

    section("4. End-To-End RAG Pipeline", story)
    story.append(pipeline_table())
    story.append(PageBreak())

    section("5. Retrieval And Reranking Logic", story)
    story.append(
        Paragraph(
            "Pinecone first retrieves semantically relevant chunks using vector similarity. The app then reranks "
            "the retrieved evidence with an explainable score that combines semantic relevance with live trend signals.",
            STYLES["Body"],
        )
    )
    story.append(
        bullets(
            [
                "Semantic relevance from Pinecone similarity.",
                "Launch recency so recent products surface more strongly.",
                "Product Hunt votes and comments as public launch traction signals.",
                "Source diversity when evidence comes from more than one source type.",
                "Evidence count when multiple chunks support the same startup.",
                "Sector or region match when user intent includes a domain or geography.",
            ],
            STYLES["Body"],
        )
    )
    story.append(Spacer(1, 8))

    section("6. What The Dashboard Shows", story)
    story.append(
        bullets(
            [
                "Chat-style question and answer flow for multiple questions.",
                "Suggested questions to support a smooth project demonstration.",
                "Live Gemini answer generation with cited evidence.",
                "Ranked startup table and trend charts.",
                "Behind-the-scenes RAG trace for each question.",
                "Exact LLM prompt so reviewers can inspect grounding and limitations.",
            ],
            STYLES["Body"],
        )
    )
    story.append(Spacer(1, 8))

    section("7. Why This Is A Strong RAG Submission", story)
    story.append(
        bullets(
            [
                "It uses real external data instead of only static documents.",
                "It includes chunking, embeddings, vectorization, retrieval, reranking, and answer generation.",
                "It uses Pinecone as the live vector store and Gemini for both embeddings and answers.",
                "It includes transparent traceability, which is valuable for debugging and evaluation.",
                "It avoids unsupported claims about funding, valuation, revenue, or investment outcomes.",
            ],
            STYLES["Body"],
        )
    )
    story.append(Spacer(1, 8))

    section("8. Limitations And Future Scope", story)
    story.append(
        Paragraph(
            "The app is an exploratory intelligence tool, not an investment advisor. Product Hunt favors launched "
            "products and technical audiences, while company websites can be marketing-heavy. The trend score is a "
            "transparent heuristic rather than a prediction of future success.",
            STYLES["Body"],
        )
    )
    story.append(
        bullets(
            [
                "Add startup news, accelerator profiles, and reliable funding data.",
                "Move indexing to a scheduled background job for production use.",
                "Add persistent user sessions and saved research boards.",
                "Evaluate retrieval quality with benchmark questions and expected evidence.",
                "Experiment with more advanced reranking models.",
            ],
            STYLES["Body"],
        )
    )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


BASE_STYLES = getSampleStyleSheet()
STYLES = {
    "CoverTitle": ParagraphStyle(
        "CoverTitle",
        parent=BASE_STYLES["Title"],
        fontName="Helvetica-Bold",
        fontSize=30,
        leading=36,
        textColor=colors.HexColor("#17202A"),
        alignment=TA_CENTER,
        spaceAfter=8,
    ),
    "CoverSubtitle": ParagraphStyle(
        "CoverSubtitle",
        parent=BASE_STYLES["Normal"],
        fontName="Helvetica",
        fontSize=15,
        leading=20,
        textColor=colors.HexColor("#5E6874"),
        alignment=TA_CENTER,
        spaceAfter=16,
    ),
    "Lead": ParagraphStyle(
        "Lead",
        parent=BASE_STYLES["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17202A"),
        spaceAfter=10,
    ),
    "SectionTitle": ParagraphStyle(
        "SectionTitle",
        parent=BASE_STYLES["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#17202A"),
        spaceBefore=8,
        spaceAfter=3,
    ),
    "Body": ParagraphStyle(
        "Body",
        parent=BASE_STYLES["BodyText"],
        fontName="Helvetica",
        fontSize=9.8,
        leading=14.2,
        textColor=colors.HexColor("#17202A"),
        alignment=TA_LEFT,
        spaceAfter=6,
    ),
}


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT_PATH)
