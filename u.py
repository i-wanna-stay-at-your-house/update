import streamlit as st
from streamlit_mic_recorder import mic_recorder
import whisper
import tempfile
import openai
import os
import warnings
import base64

# Suppress FP16 warning
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# Load the Whisper model
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

model = load_whisper_model()

# Set OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
openai.api_key = api_key

def transcribe_audio(file_path):
    result = model.transcribe(file_path)
    return result['text']

def gpt_call(text, selected_language):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"Translate the following text to {selected_language}. If the text contains multiple languages, translate them accordingly."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message['content']

# 이미지 Base64 인코딩
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

img_file = r'C:\Users\user\Desktop\경희대\학부연구생\b64356e6-f699-44ea-a49b-5595e4511d86.jpeg'

if not os.path.exists(img_file):
    st.error(f"File not found: {img_file}")
else:
    img_base64 = get_base64_of_bin_file(img_file)

    st.markdown(f"""
    <style>
    .stApp {{
        background : url('data:image/jpeg;base64,{img_base64}');
        background-size: cover;
        font-family: Arial, Helvetica, sans-serif;
    }}
    .title {{
        font-size: 60px;
        font-weight: bold;
        color: #f7e600;
    }}
    .stTextInput>div>input {{
        background-color: lightblue !important;
        color: black !important;
    }}
    .stSelectbox>div {{
        border-radius : 15px !important;
    }}
    .stSelectbox>div:hover {{
        background-color: lightblue !important;
    }}
    .stSelectbox>div>select {{
        background-color: lightblue !important;
        color: black !important;
        border: 2px solid black !important;
    }}
    .card {{
        background: white !important;
        color : #4B89DC;
        font-size : 40px;
        padding: 1em !important;
        margin: 1em 0 !important;
        border-radius: 15px !important;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.3) !important;
    }}
    .big-font {{
        font-size: 20px !important;
    }}
    .center-content {{
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }}
    .translation {{
        color: blue !important;
    }}
    </style>
    <script>
    // JavaScript to add hover functionality for select box
    document.addEventListener('DOMContentLoaded', function() {{
        var selectBox = document.querySelector('.stSelectbox div');
        selectBox.addEventListener('mouseover', function() {{
            var selectElement = this.querySelector('select');
            var event = new MouseEvent('mousedown', {{
                view: window,
                bubbles: true,
                cancelable: true
            }});
            selectElement.dispatchEvent(event);
        }});
    }});
    </script>
    """, unsafe_allow_html=True)

    st.markdown('<div class="title">Streamlit Audio Translator</div>', unsafe_allow_html=True)

    st.write("Select the language of the translation result and click Start!")
    # 선택할 수 있는 언어 목록
    languages = ['한국어', 'English', '中文', '日本語', 'Tiếng Việt', 'हिन्दी']

    # Initialize session state for selected language
    if 'selected_language' not in st.session_state:
        st.session_state.selected_language = 'English'

    # 언어 선택 박스 (기본값을 영어로 설정)
    selected_language = st.selectbox('Language', languages, index=1)

    # Check if the selected language has changed
    if selected_language != st.session_state.selected_language:
        st.session_state.selected_language = selected_language

    audio = mic_recorder(start_prompt="Start", stop_prompt="Stop", format="webm", just_once=True)

    if audio:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_wav_file:
            tmp_wav_file.write(audio["bytes"])
            tmp_wav_file.flush()
            file_path = tmp_wav_file.name

        st.audio(file_path, format='audio/webm')
        transcription = transcribe_audio(file_path)
        ts_text = gpt_call(transcription, selected_language)
        st.write("Transcription:")
        st.write(transcription)
        st.markdown(f'<div class="card"><h2>Translation</h2><p>{ts_text}</p></div>', unsafe_allow_html=True)

        # Convert translated text to speech (if TTS is implemented)
        # tts_audio_data = text_to_speech(client, ts_text)

        # Automatically play the TTS audio if available
        # if tts_audio_data:
        #     st.audio(tts_audio_data, format='audio/mp3', autoplay=True)

        # Delete temporary files
        os.remove(file_path)
        # if tts_audio_data:
        #     os.remove(tts_audio_data)
