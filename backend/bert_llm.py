from transformers import AutoTokenizer,AutoModelForSequenceClassification
import torch
from langchain_community.chat_models import ChatLlamaCpp
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph,START,END
from typing import Annotated, Optional 
from typing_extensions import TypedDict
import pandas as pd
from langgraph.checkpoint.memory import MemorySaver
import os # 파일 경로 확인용
from io import StringIO # StringIO 추가 (FutureWarning 제거용)

# === Graph State 정의 ====
class State(TypedDict):
    path: Annotated[str, '파일 위치'] 
    doll_id : Annotated[int,'id']
    df_merged: Optional[str] 
    summary_report: Optional[str] 

class BertLlm:
    # llm 프롬프트는 클래스 상수로 정의 (수정 없음)
    system_prompt = """
    당신은 등급 판별자가 아닙니다. 이미 다른 시스템이 문장의 위험 등급을 판정했습니다. 
    당신의 임무는 **판단된 등급을 그대로 유지한 채**, 그 이유만 논리적으로 설명하는 것입니다. 
    새로운 판단, 재분류, 반박, 평가를 해서는 안 됩니다.

    - 위험 등급 순서: positive → danger → critical → emergency 
    - 위험 등급 정의:
        • positive: 정서적으로 안정적이며 긍정적인 감정을 표현한 상태. 희망·감사·행복 등의 표현을 포함. 예: "오늘 기분이 좋아."
        • danger: 불안·무기력 등 부정적 감정이 드러나지만 즉각적인 위험은 없는 상태. 예: "요즘 아무 의욕이 없어."
        • critical: 절망·자책 등 심리적 위기 신호가 명확히 드러나는 상태. 예: "이젠 아무 의미가 없어."
        • emergency: 자살·자해 등 즉각적인 개입이 필요한 긴급 위험 상태. 예: "지금이라도 끝내고 싶어."

    - 이 문장은 이미 "{answer}" 등급으로 분류되었습니다. 
    - 당신은 이 결과를 그대로 인정해야 하며, 절대 다른 등급으로 판단하거나 부정하지 마십시오.

    분석 대상 문장:
    "{text}"

    출력 형식(이 형식을 반드시 그대로 따르십시오):
    판단 근거: (해당 문장이 '{answer}' 등급으로 분류된 이유를 설명. 
    이유는 반드시 '{answer}'가 맞다는 방향으로 작성해야 하며, 부정하거나 반박하지 마십시오.)
    """

    # 종합 보고서용 시스템 프롬프트 (수정 없음)
    summary_system_prompt = """
    당신은 데이터 분석가이자 임상 심리 전문가입니다.
    당신의 임무는 {doll_id} 님의 대화 기록을 분석하여, 시간 흐름에 따른 감정 변화와 주요 위험 징후를 요약하는 4000자 이내 '종합 보고서'를 작성하는 것입니다.

    입력 데이터는 [날짜, 위험등급, 발화내용] 형식으로 제공됩니다.
    위험 등급 순서: positive(안정) → danger(불안) → critical(위기) → emergency(긴급)
    단 이것은 이들을 관리하는 보호자나 시 공무원이 봐야 하는 것이야 특히 긴급이면 바로 연락부탁드린다는 내용을 담아야 해 

    보고서에 포함되어야 할 내용:
    1.  **전반적인 요약 (Overall Summary):** 대상자의 현재 심리 상태에 대한 전반적인 평가.
    2.  **주요 감정 추세 (Emotional Trend):** 시간(날짜)이 지남에 따라 감정이 긍정적으로 변하는지, 부정적으로 변하는지, 혹은 특정 패턴이 있는지 분석합니다.
    3.  **주요 위험 징후 (Key Risk Factors):** 'critical' 또는 'emergency' 등급이 관찰된 경우, 해당 발화의 핵심 내용을 요약하고 이것이 무엇을 의미하는지 분석합니다.
    4.  **주요 발화 주제 (Main Topics):** 대상자가 주로 이야기하는 주제(예: 무기력, 관계, 미래에 대한 불안 등)가 무엇인지 파악합니다.

    [분석 대상 데이터]
    {analysis_data}

    [보고서]
    (여기에 종합 보고서를 작성하십시오.)
    """
    
    def __init__(self, bert_path: str, bert_weights: str, llm_path: str):
        print("모델 로딩을 시작합니다...")
        
        # === 모델 로드 ===
        self.tokenizer, self.model = self.load_bert(bert_path, bert_weights)
        self.raw_llm = self.load_llm(llm_path)
        
        self.ranks = ['positive', 'danger', 'critical', 'emergency']
        
        # === LLM 프롬프트 템플릿 생성 ===
        self.llm_prompt_template = ChatPromptTemplate.from_messages([
            ('system', self.system_prompt),
            ('user', "{input}"),
        ])
        
        # 보고서용 프롬프트 템플릿 초기화
        self.summary_prompt_template = ChatPromptTemplate.from_messages([
            ('system', self.summary_system_prompt),
            ('user', "{input}"), 
        ])

        # === 그래프 빌드 및 컴파일 ===
        self.app = self._build_graph()
        print("그래프 컴파일 및 실행 준비 완료.")


    # bert 모델 불러오기 (수정 없음)
    def load_bert(self, best_path, best_weight_path):
        tokenizer = AutoTokenizer.from_pretrained(best_path)
        model = AutoModelForSequenceClassification.from_pretrained(best_path, num_labels=4)
        
        state_dict = torch.load(best_weight_path, map_location="cpu")
        state_dict = state_dict["model_state_dict"]
        model.load_state_dict(state_dict)
        model.eval()
        print("BERT 오프라인 로드 성공")

        return tokenizer, model 
    
    # llm 모델 불러오기 (수정 없음)
    def load_llm(self, llm_path):
        raw_llm = ChatLlamaCpp(
            model_path= llm_path,
            n_ctx=4096,
            n_gpu_layers=35,
            temperature=0.0,
            verbose=False,
        )
        print("GGUF LLM 로드 성공")
        return raw_llm
    
    # 그래프 구조 (수정 없음)
    def _build_graph(self):
        graph = StateGraph(State)
        
        graph.add_node("node_file_analysis", self.node_file_analysis)
        graph.add_node("node_mode_analysis", self.node_mode_analysis)
        graph.add_node("node_summary_report", self.node_summary_report) 
        
        graph.add_edge(START,"node_file_analysis")
        graph.add_edge('node_file_analysis',"node_mode_analysis")
        
        graph.add_edge("node_mode_analysis","node_summary_report")
        graph.add_edge("node_summary_report", END)

        memory = MemorySaver()
        app = graph.compile(checkpointer=memory)
        return app

    # --- 노드 함수들 ---

    '''[노드 1] 대화턴 연결'''
    def node_file_analysis(self, state:State)->State:
        print("--- [Node 1] 파일 분석 및 대화 병합 중... ---")
        df = pd.read_excel(state['path'])
        df = df[df['doll_id'] ==  state["doll_id"]].copy()
        df['uttered_at'] = pd.to_datetime(df['uttered_at'])
        
        # 💡 수정: 필터링된 데이터프레임 전체를 sub으로 사용합니다.
        sub = df
        
        sub['min'] = sub['uttered_at'].diff() > pd.Timedelta(minutes=10)
        sub["group"] = sub["min"].cumsum()

        merged = (
            sub.groupby(["group", "min"])
            .agg({
                "text": lambda x: " ".join(x) if not x.empty else "",
                "uttered_at": "first"
            })
            .reset_index(drop=True)
        )

        merged['doll_id'] = state['doll_id'] # 👈 State에서 ID 사용
        merge_df = merged
        df_json_str = merge_df.to_json(orient='split', date_format='iso')
        
        return {"df_merged": df_json_str}


    '''[노드 2] 감정 분석 및 근거 생성'''
    def node_mode_analysis(self, state:State)->State:
        print("--- [Node 2] BERT 분석 및 LLM 근거 생성 중... ---")
        # 💡 수정: StringIO를 사용하여 FutureWarning 제거
        df_restored = pd.read_json(
            StringIO(state['df_merged']), # 👈 StringIO 사용
            orient='split', 
            convert_dates=['uttered_at']
        )
        print(df_restored)
        
        llm_answers = []
        bert_ranks = []

        for text in df_restored['text']:
            inputs = self.tokenizer(text, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model(**inputs)

            answer = self.ranks[outputs.logits[0].argmax()]
            bert_ranks.append(answer)

            messages = self.llm_prompt_template.format_messages(
                answer=answer,
                text=text,
                input=text
            )

            response = self.raw_llm.invoke(messages)
            llm_answers.append(response.content) 

        df_restored['bert_grade'] = bert_ranks
        df_restored['llm_reason'] = llm_answers
        df_restored = df_restored[['text','uttered_at','bert_grade','llm_reason']].copy()
        df_restored.columns = ['발화문','발화시간','등급','추론이유']
        df_restored['발화시간'] = pd.to_datetime(df_restored['발화시간']).dt.date
        
        # 💡 수정: 다음 노드에 전달할 JSON 문자열을 생성하고 State에 저장
        df_json_str = df_restored.to_json(orient='split', date_format='iso')
        
        return {"df_merged": df_json_str}
    
    
    '''[노드 3] 종합 보고서 생성'''
    def node_summary_report(self, state: State) -> State:
        print("--- [Node 3] 종합 보고서 생성 중... ---")
        
        # 1. 이전 노드에서 분석한 데이터 로드
        # 💡 수정: StringIO를 사용하여 FutureWarning 제거
        df = pd.read_json(
            StringIO(state['df_merged']), # 👈 StringIO 사용
            orient='split', 
            convert_dates=['발화시간']
        )
        
        # 2. LLM 입력을 위해 데이터를 단순 텍스트로 변환
        data_list = []
        for _, row in df.iterrows():
            # 날짜 형식 'YYYY-MM-DD'로 고정
            date_str = row['발화시간'].strftime('%Y-%m-%d')
            
            # 💡 수정: .copy() 제거 및 전체 문자열 할당
            full_text = row['발화문']
            
            data_list.append(
                f"[날짜: {date_str}, 등급: {row['등급']}, 내용: {full_text}]" # 👈 전체 문자열 사용
            )
            
        
        analysis_data_str = "\n".join(data_list)
        print(analysis_data_str)
        if not analysis_data_str:
            analysis_data_str = "분석할 데이터가 없습니다."
            
        # 3. 보고서 생성용 LLM 호출
        messages = self.summary_prompt_template.format_messages(
            doll_id=state['doll_id'],
            analysis_data=analysis_data_str,
            input=analysis_data_str 
        )
        
        response = self.raw_llm.invoke(messages)
        summary_report = response.content
        
        print("--- [생성된 종합 보고서] ---")
        print(summary_report)
        print("---------------------------")
        
        # 4. 최종 상태 반환: df_merged를 유지하고 summary_report를 추가하여 반환합니다.
        return {"summary_report": summary_report, "df_merged": state['df_merged']}


    # --- 클래스 실행을 위한 public 메서드 ---
    def run_analysis(self, file_path: str, doll_id:int, thread_id: str = "default_thread"):
        """분석 그래프를 실행하고 '최종 State 딕셔너리' 전체를 반환합니다."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"입력 파일이 없습니다: {file_path}")
            
        print(f"--- 분석 시작 (Thread ID: {thread_id}) ---")
        config = {"configurable": {"thread_id": thread_id}}
          
        initial_state = {"path": file_path, 'doll_id': doll_id}
        
        final_state = self.app.invoke(initial_state, config=config)
        print("--- 분석 완료 ---")
        
        # State 딕셔너리 전체를 반환합니다.
        return final_state

    def get_dataframe_from_json(self, json_str: str) -> pd.DataFrame:
        """결과 JSON을 DataFrame으로 변환합니다."""
        # 💡 수정: StringIO를 사용하여 FutureWarning 제거
        return pd.read_json(
            StringIO(json_str), # 👈 StringIO 사용
            orient='split', 
            convert_dates=['발화시간'] 
        )

# 실행 함수 
def main(BERT_LOCAL_PATH,BERT_WEIGHTS_PATH,LLM_GGUF_PATH,INPUT_EXCEL_PATH,doll_id):
    # 1. 클래스 인스턴스 생성
    analyzer = BertLlm(
        bert_path=BERT_LOCAL_PATH,
        bert_weights=BERT_WEIGHTS_PATH,
        llm_path=LLM_GGUF_PATH
    )
    
    # 2. 분석 실행 
    final_state = analyzer.run_analysis(
        file_path=INPUT_EXCEL_PATH, 
        doll_id=doll_id,
        thread_id="test_run_01"
    )
    
    # 3. 결과 확인 
    # 3-1. 개별 분석 결과 (DataFrame) 추출
    df_json = final_state.get('df_merged')
    final_df = None
    if df_json:
        final_df = analyzer.get_dataframe_from_json(df_json)
        print("\n--- [결과 1] 개별 분석 결과 (DataFrame) ---")
        print(final_df.head())
    else:
        print("\n--- [결과 1] 개별 분석 결과(df_merged)가 없습니다. ---")
    # 3-2. 최종 종합 보고서 추출
    final_report = final_state.get('summary_report')
    if final_report:
        print("\n--- [결과 2] 최종 종합 보고서 ---")
        print(final_report)
    else:
        print("\n--- [결과 2] 최종 종합 보고서(summary_report)가 없습니다. ---")
    
    # 두 가지 결과를 모두 포함한 딕셔너리 반환
    return {
        "detail_dataframe": final_df,
        "summary_report": final_report
    }


# =================================================================
# 클래스 실행 예시 (스크립트를 직접 실행할 때)
# =================================================================
if __name__ == "__main__":
    from pathlib import Path
    # 1. 이 파일(bert_llm.py)의 절대 경로를 가져옵니다.
    SCRIPT_PATH = Path(__file__).resolve()

    # 2. 이 파일이 속한 폴더(backend)를 가져옵니다.
    BACKEND_DIR = SCRIPT_PATH.parent

    # 3. 'backend' 폴더의 부모 폴더(프로젝트 루트)를 가져옵니다.
    PROJECT_ROOT = BACKEND_DIR.parent
    print(PROJECT_ROOT)

    # 4. 프로젝트 루트를 기준으로 경로 설정
    
    BERT_LOCAL_PATH = str(PROJECT_ROOT / "backend"/"kcbert_local")
    BERT_WEIGHTS_PATH = str(PROJECT_ROOT / "backend"/"best_kcbert_model.pt")
    LLM_GGUF_PATH = str(PROJECT_ROOT / "backend"/"gemma-3-1B-it-QAT-Q4_0.gguf")
    
    # 분석할 실제 엑셀 파일 경로 (이것도 루트 기준이 좋습니다)
    INPUT_EXCEL_PATH = str(PROJECT_ROOT / "backend"/"test.xlsx") 
    DOLL_ID = 3
    # (디버깅용) 경로가 올바르게 설정되었는지 확인
    print(f"--- [테스트 모드] ---")
    print(f"프로젝트 루트: {PROJECT_ROOT}")
    print(f"LLM 경로: {LLM_GGUF_PATH}")
    print("-------------------")

    a=main(BERT_LOCAL_PATH, BERT_WEIGHTS_PATH, LLM_GGUF_PATH, INPUT_EXCEL_PATH,DOLL_ID)
    print(a)