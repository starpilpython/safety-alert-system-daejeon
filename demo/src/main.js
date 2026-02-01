const { invoke } = window.__TAURI__.core;
const { open } = window.__TAURI__.dialog;


let filePath = null
const conArray = []
let summary = "없음"

// fastapi 호출하는 함수 
async function callPredictAPI(path, doll_id) {
  const apiUrl = 'http://localhost:8000/predict';
   
  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },

      
      body: JSON.stringify({file_path:path, doll_id:doll_id,kakao_message:summary }) // 객체 생성과 동시에 전달
    }); 
    
    // 응답이 성공적이지 않으면 오류 발생
    if (!response.ok) {
      throw new Error(`HTTP 오류: ${response.status}`);
    }
    
    // 1. 성공한 경우 1차 JSON 파싱 (결과: { predicted_value: "..." })
    const result = await response.json();
    // 2. 서버 응답에 predicted_value가 있는지 확인
    if (result.predicted_value) { 
      // 2차 파싱: "predicted_value" 키 안의 'JSON 문자열'을 실제 객체로 변환
      const reportString = result.summary1;
      const finalData = result.predicted_value;
       
      console.log({detail:finalData, report:reportString})
      return {detail:finalData, report:reportString}; // 최종 파싱된 데이터 객체 반환}
    } else {
      // 서버가 예상과 다른 구조의 JSON을 보냈을 경우
      throw new Error("서버 응답에서 'predicted_value'를 찾을 수 없습니다.");
    }
  } catch (error) {
    // 오류 발생 시 콘솔에 로그만 남기고 undefined 반환
    console.error('API 호출 실패:', error);
    return undefined;
  }
}




// json을 table로 변환
async function renderTable(data) {
    const wrapper = document.getElementById("table-wrapper");
    wrapper.innerHTML = ''; // 기존 테이블이 있으면 비우기

    // 💡 수정된 부분: 전달받은 객체 (data)를 Grid.js가 원하는 2차원 배열로 변환
    const keys = ["발화문", "발화시간", "등급", "추론이유"];
    const rowIndices = Object.keys(data[keys[0]] || {}); // 첫 번째 키(발화문)에서 인덱스(0, 1, 2, ...)를 가져옴

    const convertedData = rowIndices.map(index => {
        // 각 인덱스(행)에 대해, 모든 키(열)의 값을 순서대로 배열로 만듭니다.
        return keys.map(key => data[key][index]);
    });
    
    // (선택 사항) 변환된 데이터 확인
    console.log('Grid.js에 전달할 변환된 데이터:', convertedData); 


    new gridjs.Grid({
        columns: [
            // 컬럼 정의는 그대로 유지
            { name: "발화문", width: "20%" },
            { name: "발화시간", width: "15%" },
            { name: "등급", width: "15%" },    
            { name: "추론이유", width: "50%" }, 

        ], 
        // 💡 수정: data.data 대신 변환된 배열을 사용합니다.
        data: convertedData, 
        search: false, 
        sort: false, 
        pagination: { 
            limit: 3 
        },
        style: {
            td: {
                'white-space': 'pre-wrap' 
            }
        }
    }).render(wrapper); 
}


// 본문
document.addEventListener("DOMContentLoaded", () => {

    //=============================================================
    // DOM 요소 가져오기
    const openFileBtn = document.getElementById('open-file-btn');
    const resultPath = document.getElementById('result-path');

    // 버튼 클릭 이벤트 리스너 설정
    openFileBtn.addEventListener('click', async () => {
        // Tauri dialog.open()을 호출하고 결과를 받습니다.
        const selectedPath = await open({ // 💡 변수명을 file 대신 selectedPath로 사용하여 혼동 방지
            multiple: false,
            directory: false,
            filters: [
                { // 사용자가 특정 확장자만 필터링할 수 있도록 설정
                    name: 'Excel 파일',
                    extensions: ['xlsx', 'xls']
                },
                {
                    name: '모든 파일',
                    extensions: ['*']
                }
            ]
        });

        // 1. 대화 상자를 닫았을 때 selectedPath는 null 또는 undefined일 수 있습니다.
        // 2. 단일 파일 선택 모드이므로, 선택된 경우 selectedPath는 문자열(선택된 파일의 절대 경로)입니다.
        if (selectedPath) {
            // 이벤트 리스너 내부에서 외부 변수 filePath에 값을 할당
            // Python으로 파일 전달
            filePath = selectedPath.replace(/\\/g, "\\\\");
             
            // 파일 경로 표시 로직을 파일이 '선택된 직후'에 실행
            
            resultPath.innerText = '완료함'; 
            resultPath.classList.add('blue')
            console.log(filePath)
            
            // 'grape'의 인덱스 찾기
            const index = conArray.indexOf("경로완료")

            if (index !== -1) {
            conArray.splice(index, 1) // 해당 인덱스 요소 1개 제거
            }
            conArray.push("경로완료")
            console.log(conArray)

            // 선택된 파일 경로(filePath)를 가지고 Rust 백엔드 함수(invoke)를 호출하는 등의 
            // 추가적인 작업을 여기서 수행할 수 있습니다.
            // 예시: invoke('read_excel_file', { path: filePath }); 

        } else {
            // 파일을 선택하지 않고 취소한 경우
            resultPath.innerText = '미완료';
            filePath = null; // 경로 초기화
            resultPath.classList.remove('blue')

            // 'grape'의 인덱스 찾기
            const index = conArray.indexOf("경로완료")

            if (index !== -1) {
            conArray.splice(index, 1) // 해당 인덱스 요소 1개 제거
            }
            console.log(conArray)
        }
    });

    // id 입력
    // 버튼 클릭 이벤트 리스너 설정
    const inputFileBtn = document.getElementById('input_id');
    const input = document.getElementById('input');
    const inputPath = document.getElementById('input-path');
    inputFileBtn.addEventListener('click', async () => {

        if (!input.value) {
            console.log("입력값이 비어 있음");
            inputPath.innerText = '미완료';
            inputPath.classList.remove('blue')

            // 'grape'의 인덱스 찾기
            const index = conArray.indexOf("id완료")

            if (index !== -1) {
            conArray.splice(index, 1) // 해당 인덱스 요소 1개 제거
            }
            console.log(conArray)

        } else {
            console.log("입력값 있음:", input.value);
            inputPath.innerText = '완료함';
            inputPath.classList.add('blue')


            // 'grape'의 인덱스 찾기
            const index = conArray.indexOf("id완료")

            if (index !== -1) {
            conArray.splice(index, 1) // 해당 인덱스 요소 1개 제거
            }
            conArray.push("id완료")
            console.log(conArray)
        };


        // step1과 step2를 모두 사용할 때 버튼이 나오게 하기 
        const exeBtn = document.getElementById('exe');
        function vis() {
            const checkList = ["경로완료", "id완료"]; // 둘 다 있는지 확인
            const allIncluded = checkList.every(item => conArray.includes(item));
           if (allIncluded) {
            exeBtn.classList.remove('hidden')
            }else{
            exeBtn.classList.add('hidden')
            }
        } 
        setInterval(vis,1000)

        exeBtn.addEventListener('click',async () =>{

            // fastapi로 전달
            try {
                const predictedData = await callPredictAPI(
                    filePath,    // 👈 변수 값만 전달
                    parseInt(input.value, 10)  // 👈 변수 값만 전달
                );
                //데이터가 성공적으로 오면, 테이블 생성 함수 호출
                if (predictedData) {
                    // 2-2. 반환된 객체에서 데이터 추출
                    const detail = predictedData.detail;
                    summary = predictedData.report;
                    console.log('API 호출 성공 및 분석 완료');
                    console.log(detail)
                    renderTable(detail);

                    // 완료함 표시
                    const exePath = document.getElementById('exe-path')
                    exePath.innerText = '완료함';
                    exePath.classList.remove('hidden')
                    exePath.classList.add('blue')
                }

            } catch (err) {
                console.error('API 호출 실패:', err);
            }
            }
        )

 
    kakao.addEventListener('click', async () => {

        // 1. 전역 변수에 저장된 'summary' 보고서를 가져옵니다.
        if (!summary) {
            alert("먼저 [실행] 버튼을 눌러 분석을 완료해야 합니다.");
            console.log("전송할 summary 보고서가 없습니다.");
            return; // 함수 종료
        }

        console.log("FastAPI로 전송할 보고서:", summary);

        // 2. FastAPI의 /run-workflow 엔드포인트를 호출합니다.
        try {
            const response = await fetch('http://localhost:8000/run-workflow', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json'
                },
                // (참고) Python 코드가 'InputData'를 기대하므로
                // kakao_message 외의 값들도 함께 보내줍니다.
                body: JSON.stringify({
                    file_path: filePath || "N/A", // 전역 변수 filePath
                    doll_id: parseInt(document.getElementById('input').value) || 0, // ID input 값
                    kakao_message: summary // (★중요) 전역 변수 summary
                })
            }); 

            if (!response.ok) {
                throw new Error(`HTTP 오류: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.status === "n8n 호출 성공") {
                alert("카카오톡 전송에 성공했습니다!");
                console.log("n8n 호출 성공:", result);
            } else {
                alert("n8n 호출에 실패했습니다. (콘솔 확인)");
                console.error("n8n 호출 실패:", result); 
            }
 
        } catch (error) {
            console.error('FastAPI /run-workflow 호출 실패:', error);
            alert("n8n 전송 API 호출에 실패했습니다.");
        }
    });


  
    });
});