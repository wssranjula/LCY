import streamlit as st
st.set_page_config(page_title="StyleBot - LCY AI Shopping Assistant", page_icon="👗", layout="wide")

from langchain_community.document_loaders import RecursiveUrlLoader
import re
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS

# Define the StyleBot prompt
stylebot_prompt = """
You are "StyleBot," an AI assistant for LCY  apparel e-commerce company. Your primary goal is to help customers find the perfect clothing items and provide accurate product information. You are friendly, approachable, and knowledgeable about fashion.

For each user query, you will receive relevant product information from our database. Use this information to answer the user's questions about products, provide recommendations, and assist with their shopping needs.

If the provided product information is not sufficient, you can ask the user for more details or suggest alternatives.

Start every conversation with a brief greeting: "Hi there! I’m StyleBot, your shopping assistant. How can I help you find the perfect outfit today?"
"""

# Load API keys from Streamlit secrets
google_api_key = st.secrets["GOOGLE_API_KEY"]
openai_api_key = st.secrets["OPENAI_API_KEY"]

# Initialize the LLM (Google Gemini)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",  # Compatible model
    temperature=0,
    api_key=google_api_key
)

# Define the HTML extractor
def bs4_extractor(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return re.sub(r"\n\n+", "\n\n", soup.text).strip()

# Load and index web data with OpenAI embeddings
@st.cache_resource
def load_and_index_data(url):
    try:
        loader = RecursiveUrlLoader(url, extractor=bs4_extractor)
        docs = loader.load()
        if not docs:
            raise ValueError("No documents loaded from the URL.")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",  # Lightweight OpenAI embedding model
            openai_api_key=openai_api_key
        )
        vector_store = FAISS.from_documents(docs, embeddings)
        return vector_store
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

# Initialize the vector store and retriever
url = "https://lcy.lk/"
vector_store = load_and_index_data(url)
retriever = vector_store.as_retriever(search_kwargs={"k": 3}) if vector_store else None

# Define search_products function to retrieve relevant product information
def search_products(query):
    if not retriever:
        return "Sorry, I couldn't load the product data. Please try again later."
    docs = retriever.get_relevant_documents(query)
    return "\n\n".join([doc.page_content for doc in docs]) if docs else "No relevant products found."

# Add custom CSS for styling
st.markdown("""
    <style>
        .main {
            background-color: #f5f5f5;
        }
        .stChatMessage {
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .stChatMessage.user {
            background-color: #e0f7fa;
        }
        .stChatMessage.assistant {
            background-color: #fff;
            border: 1px solid #ddd;
        }
        .stTextInput > div > div > input {
            border-radius: 5px;
            padding: 10px;
        }
        .header {
            text-align: center;
            color: #333;
            margin-bottom: 20px;
        }
        .welcome {
            text-align: center;
            color: #666;
            font-style: italic;
        }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 class='header'>👗 StyleBot - LCY Shopping Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p class='welcome'>Find the perfect outfit with ease. Let StyleBot assist you!</p>", unsafe_allow_html=True)

# Initialize session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Hi there! I’m StyleBot, your shopping assistant. How can I help you find the perfect outfit today?"})

# Display conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
user_input = st.chat_input("Type your message here... (e.g., 'I need a red dress for a party')")

if user_input:
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Show spinner while processing the response
    with st.spinner("StyleBot is finding the perfect match for you..."):
        # Retrieve relevant product information
        relevant_docs = search_products(user_input)

        # Construct messages for the LLM (system prompt + conversation history + current query with docs)
        messages = [
            ("system", stylebot_prompt),
        ] + [(msg["role"], msg["content"]) for msg in st.session_state.messages[:-1]] + [
            ("human", f"{st.session_state.messages[-1]['content']}\n\nRelevant product information: {relevant_docs}")
        ]

        # Generate response
        try:
            response = llm.invoke(messages).content
        except Exception as e:
            response = f"Sorry, something went wrong: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)