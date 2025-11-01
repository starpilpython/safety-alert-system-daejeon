# AI 기반 데스크톱 애플리케이션 기술 문서

**Version:** 0.1.0

## 1. 개요

본 프로젝트는 대전시의 발화(發話) 데이터를 기반으로, BERT와 LLM(Large Language Model)을 결합하여 실시간으로 위험 등급을 분석하고, 특정 위험 등급에 도달했을 때 자동으로 관계자에게 알림을 전송하는 AI 기반 데스크톱 알림 서비스입니다. Tauri 프레임워크를 사용하여 웹 기술(HTML, CSS, JavaScript)을 프론트엔드로, Rust를 애플리케이션 코어로 활용하며, 별도로 구성된 Python AI 서버와 연동하여 고도화된 자연어 처리 및 추론 기능을 제공합니다.

특히, 야간 등 즉각적인 대처가 어려운 상황에서 위험 상황 발생 시 1차적으로 담당 공무원, 2차적으로 보호자 등에게 자동으로 알림을 발송하며, 위급 상황 시에는 119나 112와 같은 긴급 구조 기관에 자동으로 알릴 수 있도록 설계되어 인명 및 재산 피해를 최소화하는 것을 목적으로 합니다. 사용자 인터페이스는 Tauri의 웹뷰(WebView)를 통해 렌더링되며, 실제 AI 모델 연산은 로컬 Python 서버에서 수행된 후 그 결과가 애플리케이션에 표시되는 하이브리드 아키텍처를 채택하고 있습니다.

## 2. 기술 아키텍처

본 애플리케이션은 세 가지 주요 구성 요소로 이루어져 있습니다.

```
┌──────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│   Frontend       │     │  Tauri Core (Rust)   │     │  Python AI Backend     │
│ (HTML, CSS, JS)  │◀───▶│ (Window, Commands)   │◀───▶│   (Flask/FastAPI)      │
└──────────────────┘     └──────────────────────┘     └────────────────────────┘
       ▲                         ▲                         │
       │ (Webview)               │ (System Calls)          │ (HTTP/RPC)
       ▼                         ▼                         ▼
┌──────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│   User Interface │     │   Native OS Features │     │   AI Models (LLM)      │
└──────────────────┘     └──────────────────────┘     └────────────────────────┘
```

### 2.1. Frontend (`/src`)

-   **역할**: 사용자 인터페이스(UI) 및 사용자 경험(UX)을 담당합니다.
-   **기술**: `HTML`, `CSS`, `JavaScript`를 사용하여 웹 페이지 형태로 UI를 구성합니다.
-   **실행 환경**: Tauri가 생성한 OS 네이티브 웹뷰 내에서 실행됩니다.
-   **주요 기능**:
    -   사용자 입력(텍스트 등)을 받아 Tauri Core로 전달합니다.
    -   Tauri Core로부터 받은 AI 모델의 결과값을 화면에 렌더링합니다.
    -   `@tauri-apps/api` 라이브러리를 통해 Rust 백엔드와 통신합니다.

### 2.2. Tauri Core (Rust Backend) (`/src-tauri`)

-   **역할**: 애플리케이션의 메인 로직, 시스템 접근 및 Python AI 서버와의 통신을 담당합니다.
-   **기술**: `Rust`
-   **주요 기능**:
    -   **윈도우 관리**: 데스크톱 윈도우의 생성, 크기 조절 등 생명주기를 관리합니다.
    -   **Tauri Commands**: 프론트엔드(JavaScript)에서 호출할 수 있는 Rust 함수(`#[tauri::command]`)를 정의합니다. 이 함수들은 Python AI 서버로 요청을 보내는 프록시(Proxy) 역할을 수행합니다.
    -   **Python 서버 연동**: `reqwest`와 같은 HTTP 클라이언트 라이브러리를 사용하여 `localhost`에서 실행 중인 Python AI 서버의 API를 호출하고 응답을 받아 프론트엔드로 전달합니다.
    -   **네이티브 기능**: 파일 시스템 접근, 알림 등 OS 네이티브 기능을 JavaScript API로 노출합니다.

### 2.3. Python AI Backend (`/backend`)

-   **역할**: 실제 AI 모델을 로드하고, 추론(Inference) 요청을 처리하는 API 서버입니다.
-   **기술**: `Python`, `Flask` 또는 `FastAPI` (추정), `PyTorch`
-   **주요 기능**:
    -   **AI 모델 로드**:
        -   `best_kcbert_model.pt`: `kcbert` 기반의 한국어 NLP 모델로, 텍스트 분류, 감성 분석 등에 사용될 가능성이 높습니다. PyTorch로 학습된 모델 파일입니다.
        -   `gemma-3-1B-it-QAT-Q4_0.gguf`: Google의 Gemma 경량 LLM을 GGUF 형식으로 양자화한 모델입니다. 챗봇, 텍스트 생성 등 생성형 AI 기능을 위해 사용됩니다.
    -   **API 제공**: Tauri Core(Rust)로부터 HTTP 요청을 받아 입력 데이터를 AI 모델에 전달하고, 추론 결과를 JSON 형태로 반환하는 REST API 엔드포인트를 제공합니다.
    -   **독립 실행**: Tauri 애플리케이션과는 별개의 프로세스로 실행됩니다. 따라서 애플리케이션을 사용하기 전에 반드시 Python 서버를 먼저 실행해야 합니다.

### 2.4. 자동화 및 알림 시스템

-   **n8n 연동**: 현재 n8n 워크플로우를 통해 카카오톡 메시지 송신 자동화가 구현되어 있습니다.
-   **위험 등급 알림**: 현재는 시연을 위해 수동 버튼 조작을 통해 알림을 처리하지만, 향후 위험 등급이 특정 수준에 도달했을 때 자동으로 1차 담당 공무원, 2차 보호자 등 관계자에게 알림을 발송하도록 개선할 계획입니다.
-   **긴급 상황 대응**: 특히 야간 등 즉각적인 대처가 어려운 상황에서, 시스템이 감지한 위험 등급에 따라 119 또는 112와 같은 긴급 구조 기관에 자동으로 알림을 전송하는 기능을 구현할 예정입니다.

## 3. 주요 기술 스택

| 구분                  | 기술                                                              |
| --------------------- | ----------------------------------------------------------------- |
| **Desktop Framework** | [Tauri](https://tauri.app/)                                       |
| **Frontend**          | HTML, CSS, JavaScript                                             |
| **Application Core**  | [Rust](https://www.rust-lang.org/)                                |
| **AI Backend**        | [Python](https://www.python.org/) (Flask/FastAPI), [PyTorch](https://pytorch.org/) |
| **AI Models**         | - `kcbert-base` (Korean NLP) <br> - `Gemma` (Generative LLM)      |
| **Package Manager**   | `npm` (Frontend), `cargo` (Rust), `pip` (Python)                  |

## 4. 프로젝트 구조

-   `src/`: 프론트엔드 소스 코드 (HTML, JS, CSS).
-   `src-tauri/`: Rust 백엔드(Tauri Core) 소스 코드.
    -   `src/main.rs`: Rust 애플리케이션의 진입점.
    -   `Cargo.toml`: Rust 의존성 관리.
    -   `tauri.conf.json`: Tauri 애플리케이션 설정 (윈도우, 플러그인, 권한 등).
-   `backend/`: Python AI 서버 소스 코드.
    -   `app.py`: Python 웹 서버 실행 파일.
    -   `bert_llm.py`: AI 모델 로직 구현 파일.
    -   `*.pt`, `*.gguf`: AI 모델 가중치 파일.
-   `package.json`: Node.js 프로젝트 설정 및 의존성 관리.

## 5. 설치 및 실행 방법

### 5.1. 사전 준비 사항

-   [Node.js](https://nodejs.org/) 설치
-   [Rust](https://www.rust-lang.org/tools/install) 개발 환경 설치
-   [Python](https://www.python.org/downloads/) 및 `pip` 설치

### 5.2. 의존성 설치

1.  **Frontend & Tauri 의존성 설치**
    ```bash
    npm install
    ```

2.  **Python AI Backend 의존성 설치**
    (프로젝트 루트에 `requirements.txt` 파일이 있다면)
    ```bash
    cd backend
    pip install -r requirements.txt
    cd ..
    ```
    *`requirements.txt`가 없다면 `app.py` 또는 `bert_llm.py`의 `import` 구문을 보고 필요한 라이브러리(예: `flask`, `torch`, `transformers`)를 직접 설치해야 합니다.*

### 5.3. 애플리케이션 실행

애플리케이션은 **반드시 Python AI 서버를 먼저 실행**한 후, Tauri 앱을 실행해야 정상적으로 작동합니다.

1.  **Python AI 서버 실행**
    새 터미널을 열고 다음 명령어를 실행합니다.
    ```bash
    cd backend
    python app.py
    ```

2.  **Tauri 애플리케이션 실행**
    다른 새 터미널을 열고 다음 명령어를 실행합니다.
    ```bash
    npm run tauri dev
    ```

* node_modules파일은 빠졌기 때문에 이를 감안하여 진행 필요
<br>(필요시 tauri 다시 설치 후 cargo add tauri-plugin-dialog )
```
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init()) // 이 줄 반드시 추가
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```
