import streamlit as st
from streamlit_mic_recorder import mic_recorder
import whisper
import tempfile
import openai
import os
import warnings
from pydub import AudioSegment
import subprocess
import time
import platform

# ffmpeg 경로 찾기 함수
def find_ffmpeg():
    try:
        if platform.system() == "Windows":
            ffmpeg_path = subprocess.check_output(['where', 'ffmpeg']).decode().strip().split('\r\n')[0]
        else:
            ffmpeg_path = subprocess.check_output(['which', 'ffmpeg']).decode().strip().split('\n')[0]
        return ffmpeg_path
    except subprocess.CalledProcessError:
        return None

# ffmpeg 경로 설정
ffmpeg_path = find_ffmpeg()
if ffmpeg_path:
    AudioSegment.ffmpeg = ffmpeg_path
else:
    st.error("ffmpeg 경로를 찾을 수 없습니다. ffmpeg가 설치되어 있는지 확인하세요.")

# Suppress FP16 warning
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# Load the Whisper model
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("small")

model = load_whisper_model()
api_key = os.getenv('OPENAI_API_KEY')  # 환경 변수에서 API 키를 가져옵니다.
openai.api_key = api_key

client = openai
if not api_key:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

# 벡터 스토어의 모든 파일을 삭제하는 함수
def delete_all_files_in_vector(vector_store_id, file_list):
    for file in file_list:
        file_id = file.id
        response = client.beta.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)

# openai에 업로드 된 모든 파일 삭제
def delete_all_files():
    # Get the list of all files
    files = client.files.list()
    
    # Iterate over the files and delete each one
    for file in files:
        file_id = file.id
        client.files.delete(file_id)

def delete_messages(id):
# 스레드의 메시지 목록을 불러오기
    messages = client.beta.threads.messages.list(thread_id=id)
    # 메시지 목록에서 모든 메시지 삭제하기
    for message in messages:
        message_id = message.id
        deleted_message_response = client.beta.threads.messages.delete(thread_id=id, message_id=message_id)

# Initialize openai assistent
if 'vector_store_id' not in st.session_state:
    st.session_state.vector_store_id = "vs_bHT7TcS6HrVHAYcNgeh48lKE"
    vector_store_files = client.beta.vector_stores.files.list(vector_store_id=st.session_state.vector_store_id)
    # 파일 목록에서 모든 파일 삭제하기
    #delete_all_files_in_vector(st.session_state.vector_store_id, vector_store_files)
    #delete_all_files()

if 'thread_id' not in st.session_state:
    st.session_state.thread_id = "thread_nJyOZmEHQaabCI1wcOLjzgNs"
    #delete_messages(st.session_state.thread_id)

if 'assistant_id' not in st.session_state:
    st.session_state.assistant_id = "asst_QvnqTXw1LoxeqmwHAn2IMVoW"

if 'uploader' not in st.session_state:
    st.session_state.uploader = False

if 'uploader_list' not in st.session_state:
    st.session_state.uploader_list = []

def state_uploader():
    st.session_state.uploader = True

# Initialize session state lists
if 'transcriptions' not in st.session_state:
    st.session_state.transcriptions = []
if 'file_paths' not in st.session_state:
    st.session_state.file_paths = []
if 'ts_texts' not in st.session_state:
    st.session_state.ts_texts = []
if 'tts_audio_data' not in st.session_state:
    st.session_state.tts_audio_data = []
if 'retranslated_tts_audio_data' not in st.session_state:
    st.session_state.retranslated_tts_audio_data = []

if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False

if 'once_recording' not in st.session_state:
    st.session_state.once_recording = False

if 'temp_page' not in st.session_state:
    st.session_state.temp_page = 0

if 'is_re_recording' not in st.session_state:
    st.session_state.is_re_recording = False

def transcribe_audio(file_path):
    result = model.transcribe(file_path, language='ko')
    return result['text']

def translator_call(client, text, selected_language, selected_tone):
    content = f"First Your main task is to translate given text to {selected_language}. Do not provide me with anything other than the translation. for example 저는 회계 원리를 좋아합니다 -> 我喜欢会计原理 is a very wrong example"
    if selected_tone == "Politely and Academically":
        content += "and Second, the tone of the translated sentences must be very polite and academic. this mean you can change the word to be very polite and academic"
    if selected_tone == "Angry and Fierce":
        content += "and Second, the tone of the translated sentences must be very angry and fierce. this mean you can change the word to be very angry and fierce"
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": content},
            {"role": "user", "content": text}
        ]
    )
    return completion.choices[0].message.content

def gpt_call(client, text, selected_language, selected_tone):
    thread_id = "thread_nJyOZmEHQaabCI1wcOLjzgNs"
    
    thread_message = client.beta.threads.messages.create(thread_id, role="user", content=text)    
    
    content = f"You are a presentation script maker. Access the user's statements and the given files, read them thoroughly, and if there is content in the provided files that can enrich the user's statements, use it to enhance the user's statements. Convey the enriched content exactly as it is to the user. Please translate the enriched content into {selected_language} and provide it to the user, and no other language. and Do not include automatically generated citations or references in the response under any circumstances."

    if selected_tone == "Politely and Academically":
        content += " and the tone of the translated sentences must be very polite and academic. this mean you can change the word to be very polite and academic"
    if selected_tone == "Angry and Fierce":
        content += " and the tone of the translated sentences must be very angry and fierce. this mean you can change the word to be very angry and fierce"

    #과거 recording 참조 금지
    content += "Finally, never reference the context within the thread."
    
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id="asst_QvnqTXw1LoxeqmwHAn2IMVoW", instructions=content)
    run_id = run.id
    
    # Check if the run has been completed within a short time period
    timeout = 25  # Timeout period in seconds
    interval = 0.5  # Interval period to check in seconds
    elapsed_time = 0
    
    while elapsed_time < timeout:
        time.sleep(interval)
        elapsed_time += interval
        
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run_status.status == "completed":
            thread_messages = client.beta.threads.messages.list(thread_id)
            if thread_messages.data and thread_messages.data[0].content[0].text.value:
                return thread_messages.data[0].content[0].text.value
    
    # If the message is not processed within the timeout period
    return "The process was not completed within the expected time."

def text_to_speech(client, text):
    response = client.audio.speech.create(
        model="tts-1",
        voice="echo", #voice 설정 가능하면 참 좋을텐데
        input=text
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio_file:
        response.stream_to_file(tmp_audio_file.name)
        tmp_file_name = tmp_audio_file.name
    
    return tmp_file_name

def delete_files(i):
    del st.session_state.transcriptions[i]
    del st.session_state.file_paths[i]
    del st.session_state.ts_texts[i]
    del st.session_state.tts_audio_data[i]
    del st.session_state.retranslated_tts_audio_data[i]

def state_recode():
    st.session_state.is_recording = True

def state_re_recode():
    st.session_state.is_recording = True
    st.session_state.temp_page -= 1
    delete_files(st.session_state.temp_page)
    st.session_state.is_re_recording = True

def merge_audios_with_silence(audio_files, silence_duration=700):
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=silence_duration)
    for audio_file in audio_files:
        combined += AudioSegment.from_file(audio_file) + silence
    return combined

# Streamlit interface
st.title("Streamlit Audio Translator")

st.write("Select the language of the translation result and click Start!")
st.text_area("Write your notes here:", height=200)
# 선택할 수 있는 언어 목록
languages = ['한국어', 'English', '中文', '日本語', 'Tiếng Việt', 'हिन्दी']

tones = ['Default', 'Politely and Academically']

col1_tone, col2_file_uploader = st.columns([1, 1])
with col1_tone:
    selected_tone = st.radio(label="Tone", options=tones, index=0, horizontal=True)
    use_rag = st.toggle("Using RAG")
    
if use_rag:   
    with col2_file_uploader:
        uploaded_files = st.file_uploader("Upload File", type=['txt', 'doc', 'docx', 'pdf', 'pptx'], accept_multiple_files=True, on_change=state_uploader)

        if st.session_state.uploader and len(uploaded_files) > len(st.session_state.uploader_list):

            st.session_state.uploader = False
            st.session_state.uploader_list = uploaded_files

            for uploaded_file in uploaded_files:
                # 파일을 저장할 경로 설정
                file_path = uploaded_file.name
            
                # 파일을 저장
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
                try:
                    # OpenAI API를 통해 파일 업로드
                    with open(file_path, "rb") as f:
                        response = client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                
                    # 업로드 결과 출력
                    st.write(f"파일 업로드 완료: {uploaded_file.name}")
                    st.write(response)

                    file_id = response.id

                    # 벡터 스토어에 파일 업로드
                    try:
                        vector_store_response = client.beta.vector_stores.files.create(
                            vector_store_id=st.session_state.vector_store_id,
                            file_id=file_id
                        )
                    except Exception as ve:
                        st.write(f"벡터 스토어 업로드 중 오류 발생: {file_id}")
                        st.write(ve)
                except Exception as e:
                    st.write(f"파일 업로드 중 오류가 발생했습니다: {uploaded_file.name}")
                    st.write(e)

                # finally:
                #     # 로컬 파일 삭제
                #     if os.path.exists(file_path):
                #         os.remove(file_path)
                #         st.write(f"로컬 파일 삭제 완료: {uploaded_file.name}")
                    # 중복 파일 삭제 로직
                try:
                    # OpenAI API를 통해 파일 리스트 조회
                    file_list = client.files.list()

                    # 파일 이름을 기준으로 중복 체크
                    file_names = {}
                    for file in file_list:
                        filename = file.filename
                        file_id = file.id
                        if filename in file_names:
                            # 중복된 파일 삭제
                            client.files.delete(file_id)
                            st.write(f"중복된 파일 삭제: {filename} (ID: {file_id})")
                        else:
                            file_names[filename] = file_id
                except Exception as e:
                    st.write("중복 파일 삭제 중 오류가 발생했습니다.")
                    st.write(e)

        elif len(uploaded_files) < len(st.session_state.uploader_list):
            st.session_state.uploader = False
            unique_to_list = [item for item in st.session_state.uploader_list if item not in uploaded_files]
            st.session_state.uploader_list = uploaded_files
            # OpenAI API를 통해 파일 리스트 조회
            try:
                file_list = client.files.list()
                file_list_data = file_list
                vector_store_files = client.beta.vector_stores.files.list(vector_store_id=st.session_state.vector_store_id)

                for file in file_list_data:
                    if file.filename == unique_to_list[0].name:
                        client.beta.vector_stores.files.delete(vector_store_id=st.session_state.vector_store_id, file_id=file.id)
                        client.files.delete(file.id)
                        st.write(f"OpenAI에서 파일 삭제: {unique_to_list[0].name}")

            except Exception as e:
                st.write(f"파일 삭제 중 오류가 발생했습니다: {unique_to_list[0].name}")
                st.write(e)

# 언어 선택 박스 (기본값을 영어로 설정)
selected_language = st.selectbox('Language', languages, index=1)

col1_audio, col2_audio = st.columns([1, 3])

with col1_audio:
    audio = mic_recorder(start_prompt=f"Start R{st.session_state.temp_page+1} Recording", stop_prompt="Stop", format="webm", callback=state_recode)

with col2_audio:
    if st.session_state.transcriptions:
        re_audio = mic_recorder(start_prompt="Re-record", stop_prompt="Stop", format="webm", callback=state_re_recode)

if st.session_state.is_recording == True:
    st.session_state.once_recording = True
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_wav_file:
        if st.session_state.is_re_recording == False:
            tmp_wav_file.write(audio["bytes"])
        else:
            tmp_wav_file.write(re_audio["bytes"])
            st.session_state.is_re_recording = False

        tmp_wav_file.flush()
        st.session_state.file_path = tmp_wav_file.name

    # Initialize progress bar
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Transcribe audio
    progress_text.text("Transcribing audio...")
    transcription = transcribe_audio(st.session_state.file_path)
    progress_bar.progress(33)

    # Translate text
    progress_text.text("Translating text...")
    if use_rag:
        ts_text = gpt_call(client, transcription, selected_language, selected_tone)
    else:
        ts_text = translator_call(client, transcription, selected_language, selected_tone)
    progress_bar.progress(66)

    # Convert translated text to speech
    progress_text.text("Converting text to speech...")
    tts_audio = text_to_speech(client, ts_text)
    progress_bar.progress(100)

    # Append results to session state lists
    st.session_state.transcriptions.insert(st.session_state.temp_page, transcription)
    st.session_state.file_paths.insert(st.session_state.temp_page, st.session_state.file_path)
    st.session_state.ts_texts.insert(st.session_state.temp_page, ts_text)
    st.session_state.tts_audio_data.insert(st.session_state.temp_page, tts_audio)
    st.session_state.retranslated_tts_audio_data.insert(st.session_state.temp_page, tts_audio)

    #temp_Page
    st.session_state.temp_page += 1

    st.session_state.is_recording = False
    st.rerun()

st.sidebar.title("Recordings")

if st.session_state.once_recording == True and st.session_state.transcriptions:

    for i in range(len(st.session_state.transcriptions)):
        button_label = f"R{i+1}: {st.session_state.transcriptions[i][:11]}"
        if len(st.session_state.transcriptions[i]) > 11:
            button_label += ".."
        if st.sidebar.button(button_label):
            st.session_state.temp_page = i+1
            st.rerun()

    for i in range(len(st.session_state.transcriptions)):
        if st.session_state.temp_page == i+1:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"Transcription {i+1}:")
                st.write(st.session_state.transcriptions[i])
                st.audio(st.session_state.file_paths[i], format='audio/webm')

                st.write(f"Translation {i+1}:")
                st.write(st.session_state.ts_texts[i])
                st.audio(st.session_state.tts_audio_data[i], format='audio/mp3', autoplay=True)
            
            with col2:
                st.write("Tools")
                if st.button("Listen to all saved audio"):
                    audio_files = [st.session_state.tts_audio_data[i] for i in range(len(st.session_state.tts_audio_data))]
                    merged_audio = merge_audios_with_silence(audio_files)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                        merged_audio.export(tmp_file.name, format="mp3")
                        tmp_file_path = tmp_file.name

                      # 임시 파일을 바이너리로 읽어오기
                    with open(tmp_file_path, "rb") as file:
                        audio_bytes = file.read()

                    st.audio(tmp_file_path, format='audio/mp3', autoplay=True)

                      # 다운로드 버튼 추가
                    st.download_button(
                        label="Download Full Audio",
                        data=audio_bytes,
                        file_name="merged_audio.mp3",
                        mime="audio/mp3",
                        type="primary"
                    )

                excluded_list = [j+1 for j in range(len(st.session_state.transcriptions)) if j != i]

                if 'delete_confirm' not in st.session_state:
                    st.session_state.delete_confirm = False

                if st.button(f"Delete R{st.session_state.temp_page} recording"):
                    st.session_state.delete_confirm = True

                if st.session_state.delete_confirm:
                    st.warning("Are you sure you want to delete it?")
                    if st.button("Yes, delete it"):
                        delete_files(i)
                        st.session_state.delete_confirm = False
                        if st.session_state.temp_page != 1 or not st.session_state.transcriptions:
                            st.session_state.temp_page -= 1
                        st.rerun()
                    if st.button("No, keep it"):
                        st.session_state.delete_confirm = False
                        st.rerun()

                if excluded_list:
                    # Change audio order
                    change_option = st.selectbox("Reorder recordings", excluded_list, index=None, placeholder="Select the Recording")
                    
                    # Move the recording
                    if change_option:
                        change_option -= 1
                        st.session_state.transcriptions.insert(change_option, st.session_state.transcriptions.pop(i))
                        st.session_state.file_paths.insert(change_option, st.session_state.file_paths.pop(i))
                        st.session_state.ts_texts.insert(change_option, st.session_state.ts_texts.pop(i))
                        st.session_state.tts_audio_data.insert(change_option, st.session_state.tts_audio_data.pop(i))
                        st.session_state.retranslated_tts_audio_data.insert(change_option, st.session_state.retranslated_tts_audio_data.pop(i))
                        st.session_state.temp_page = change_option + 1
                        st.rerun()

# 오른쪽 밑에 Transcriptions 리스트를 줄바꿈하여 한 번에 볼 수 있는 버튼 추가
if st.session_state.transcriptions:
    with st.expander("View All Transcriptions", expanded=False):
        transcriptions_text = "\n\n".join(st.session_state.transcriptions)
        st.text_area("All Transcriptions", value=transcriptions_text, height=200)

        # 개별 transcription에 대해 재번역할 수 있는 기능 추가
        for i, transcription in enumerate(st.session_state.transcriptions):
            selected_language_retranslate = st.selectbox(f'Retranslate R{i+1}', languages, key=f'retranslate_{i}')
            if st.button(f'Translate R{i+1}', key=f'translate_button_{i}'):
                with st.spinner(f'Translating R{i+1} to {selected_language_retranslate}...'):
                    if use_rag:
                        retranslated_text = gpt_call(client, transcription, selected_language_retranslate, selected_tone)
                    else:
                        retranslated_text = translator_call(client, transcription, selected_language_retranslate, selected_tone)
                    
                    retranslated_tts_audio = text_to_speech(client, retranslated_text)
                    st.session_state.retranslated_tts_audio_data[i] = retranslated_tts_audio

                    st.session_state.ts_texts[i] = retranslated_text
                    st.write(f'Retranslated R{i+1} to {selected_language_retranslate}:')
                    st.write(retranslated_text)
                    st.audio(retranslated_tts_audio, format='audio/mp3', autoplay=True)

# 하단 고정 텍스트와 스타일 조정
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Futura:wght@300;400;700&display=swap');

    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #734954;
        color: #F2F2F2;
        text-align: right;
        padding: 10px;
        border-top: 1px solid #F2F2F2;
        font-family: 'Futura', sans-serif; /* 폰트 패밀리 변경 */
        font-size: 12px; /* 폰트 크기 변경 */
        font-style: italic; /* 폰트 스타일 변경 */
    }
    .stApp {
        background-color: #A67676; /* 원하는 색상 코드로 변경 */
    }
    section[data-testid="stSidebar"] {
        width: 150px !important; # Set the width to your desired value
    }
    </style>
    <div class="footer">
        Digital Wellness Lab 2024<br>
        Business Analytics, School of Management<br>
        Kyung Hee University<br>
        Maintained by H-.M-. Kim & S-.W-. Kim
    </div>
    """,
    unsafe_allow_html=True
)
