import json
from google import genai
from google.genai import types
import urllib.parse
import streamlit as st 

from twilio.rest import Client as TwilioClient

from  prompts  import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE, SUMMARY_REQUEST_PROMPT



GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_NUMBER = st.secrets["TWILIO_WHATSAPP_NUMBER"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


twilio_client = get_twilio_client()
gemini_client = get_gemini_client()

MODEL_NAME = "gemini-3.1-flash-lite"


def clean_whatsapp_text(text):
    if not text:
        return "no  answer generated."
    text = " ".join(text.split())
    return text[:1600] + "..." if len(text) > 1600 else text


def send_whatsapp(to_number, user_name, summary):
    try:
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to_number}",
            body=f"Hi {user_name}! Your HomeworkVision summary:\n\n{clean_whatsapp_text(summary)}",
        )
        return True, message.sid
    except Exception as error:
        return False, "v2: " + str(error)




def render_messages(messages):
    with st.chat_message(messages["role"]):
        if messages["kind"] == "text":
            st.write(messages["content"])
        elif messages["kind"] == "image":
            st.image(messages["content"])
        

def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_messages(st.session_state.messages[-1])
def ask_gemini(parts):
    try:
        return st.session_state.chat. send_message(parts).text
    except Exception as error:
        return f"sorry,something went wrong : {error}"
#step 1: onbording (username and phone)
if 'onboarded' not in st.session_state:
    st.title("HomeworkVision 📚")
    st.caption("Your friendly AI homework assistant for Math and Science problems.")

    with st.form("onboarding_form"):
        name = st.text_input("your name")
        whatsapp_number = st.text_input("" \
            "whatsapp number(with country code)",
             placeholder="+91 1234567890",
             help= "This is the number where you will receive your homework solutions. Please enter a valid WhatsApp number with the country code."
        )
        submitted = st.form_submit_button("Let's get started!")

        if submitted:
            if not name .strip() or not whatsapp_number.strip():
                st.warning
                ("Please enter both your name and WhatsApp number.")
            else:
                st.session_state.name= name.strip()
                st.session_state.whatsapp_number= whatsapp_number.strip()
                #activate my ai 
                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()
    st.stop()

    # create  chat interface


header_col, button_col = st.columns([5, 2], vertical_alignment="center")

with header_col:
    st.title("HomeworkVision 📚")


with button_col:
    send_disabled = len(st.session_state.messages) <= 1
    if st.button("send to whatsApp", disabled=send_disabled, use_container_width=True):
        with st.spinner("Summarizing your homework problems..."):
            st.session_state.summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
    if st.session_state.get("summary"):
        text = f"Hi {st.session_state.name}! Your HomeworkVision summary:\n\n{clean_whatsapp_text(st.session_state.summary)}"
        number = st.session_state.whatsapp_number.replace("+", "").replace(" ", "")
        link = f"https://wa.me/{number}?text={urllib.parse.quote(text)}"
        st.link_button("Open WhatsApp", link, use_container_width=True)

st.caption(f"Logged in as: {st.session_state.name} - updates go to: {st.session_state.whatsapp_number}")


if not st.session_state.messages:
    add_message("assistant",  "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_messages(message)  

user_input = st.chat_input(
    "Ask a question, or attach a photo of your homework problem (Math or Science)",
    accept_file= True,
    file_type=["png", "jpeg", "jpg"],
)
if user_input:
    photo = user_input.files[0] if user_input.files else None
    text= user_input.text
    parts=[]


    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type or "image/jpeg"))
    if text:
        add_message("user","text",text)
        parts.append(text)
    elif photo is not None:
        parts.append("Please read the homework question in this photo and solve it step-by-step. Reply in the same language the question is written in.")
    with st.spinner("Crunching the numbers..."):
        answer = ask_gemini(parts)
    add_message("assistant", "text", answer)
    st.rerun()
