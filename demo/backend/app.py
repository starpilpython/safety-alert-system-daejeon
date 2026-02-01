from fastapi import FastAPI
from pydantic import BaseModel
from bert_llm import main
from fastapi.middleware.cors import CORSMiddleware  # CORS 미들웨어를 임포트합니다
import httpx 
from pathlib import Path

'''n8n은 별도 워크플로우 생성'''
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/tauri" # n8n Webhook 주소

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 3. 모든 출처(Origin)를 허용합니다. (개발용)
    allow_credentials=True,
    allow_methods=["*"],  # 4. 모든 HTTP 메서드(POST, GET, OPTIONS 등)를 허용합니다.
    allow_headers=["*"],  # 5. 모든 헤더를 허용합니다.
)

# 입력 데이터 구조 정의
class InputData(BaseModel):
    file_path: str
    doll_id:int
    kakao_message:str

# 기본 경로
@app.get("/")
def root():
    return {"message": "FastAPI is running"}

# POST 예시 엔드포인트
@app.post("/predict")
def predict(data: InputData):


    # 1. 이 파일(bert_llm.py)의 절대 경로를 가져옵니다.
    SCRIPT_PATH = Path(__file__).resolve()

    # 2. 이 파일이 속한 폴더(backend)를 가져옵니다.
    BACKEND_DIR = SCRIPT_PATH.parent

    # 3. 'backend' 폴더의 부모 폴더(프로젝트 루트)를 가져옵니다.
    PROJECT_ROOT = BACKEND_DIR.parent
    print(PROJECT_ROOT)

    # 4. 프로젝트 루트를 기준으로 경로 설정
    '''해당 부분 모델 기입 필요'''
    BERT_LOCAL_PATH = str(PROJECT_ROOT / "backend"/"kcbert_local")
    BERT_WEIGHTS_PATH = str(PROJECT_ROOT / "backend"/"best_kcbert_model.pt")
    LLM_GGUF_PATH = str(PROJECT_ROOT / "backend"/"gemma-3-1B-it-QAT-Q4_0.gguf")

    # 분석할 실제 엑셀 파일 경로 (이것도 루트 기준이 좋습니다)
    INPUT_EXCEL_PATH = data.file_path 
    DOLL_ID = data.doll_id

    # 실행
    try:
        final_json_result2 = main(BERT_LOCAL_PATH, BERT_WEIGHTS_PATH, LLM_GGUF_PATH, INPUT_EXCEL_PATH,DOLL_ID)
        print(final_json_result2)
        final_json_result = final_json_result2['detail_dataframe']
        final_json_report = final_json_result2['summary_report']
       
    except:
        final_json_result = '오류가 발생했습니다'
        final_json_report = '오류가 발생했습니다'
        print(final_json_report)
     
    return {"predicted_value": final_json_result,"summary1":final_json_report}


@app.post("/run-workflow") # HTML이 호출할 주소
async def trigger_n8n_workflow(data: InputData):
    """
    HTML에서 데이터를 받아서 n8n Webhook으로 POST 요청을 보냅니다.
    """
    print(f"FastAPI가 HTML로부터 받은 데이터: {data.kakao_message}")

    # n8n으로 보낼 데이터 (받은 그대로 전달)
    n8n_data = data.kakao_message

    try:
        # httpx를 사용해 n8n Webhook을 비동기로 호출
        async with httpx.AsyncClient() as client:
            response = await client.post(N8N_WEBHOOK_URL, json=n8n_data)

        # n8n이 응답한 결과 반환
        return {"status": "n8n 호출 성공", "n8n_response": response.status_code}

    except Exception as e:
        # n8n 호출 실패 시
        return {"status": "n8n 호출 실패", "error": str(e)}