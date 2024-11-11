from flask import Flask, request, render_template
from bs4 import BeautifulSoup
import requests
from openai import OpenAI
from urllib.parse import urlparse

client = OpenAI()

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        summary = get_summary(url)
        
        # Primer prompt para obtener el mensaje de autenticidad
        authenticity_message = check_authenticity_message(summary)
        
        # Verificación de palabras clave en fuentes confiables
        keyword_match = validate_with_trusted_sources(summary)
        
        # Segundo prompt para obtener solo la probabilidad de autenticidad incluyendo el sitio
        probability = get_authenticity_probability(authenticity_message, keyword_match, url)

        # Convertir probabilidad y clasificar noticia 
        try:
            probability = float(probability)
            if probability >= 0.7:
                authenticity_status = "True"
            elif probability > 0.5:
                authenticity_status = "not sure"
            else:
                authenticity_status = "fake"
        except ValueError:
            authenticity_status = "error"

        return render_template("index.html", summary=summary, authenticity_message=authenticity_message, probability=probability, authenticity_status=authenticity_status)

    return render_template("index.html")



def get_summary(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    paragraphs = soup.find_all("p")
    summary = " ".join([para.get_text() for para in paragraphs[:3]])  # Tomamos los primeros párrafos para un resumen
    return summary

def check_authenticity_message(content):
    instruction = (
        "Evaluate the credibility of the following summary based on reliable sources (Wikipedia, BBC, and trusted sources). "
        "Provide a detailed authenticity message, noting any inconsistencies or potential red flags."
    )
    
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a checker verifying news credibility."},
            {
                "role": "user",
                "content": f"Based on the following text, {content}, provide an authenticity message argument or justification, check if there's political biased info: {instruction}"
            }
        ]
    )

    authenticity_message = completion.choices[0].message.content
    return authenticity_message

def validate_with_trusted_sources(summary):
    keywords = extract_keywords(summary)
    trusted_sites = [
        "https://www.cnn.com",
        "https://www.milenio.com",
        "https://www.imagentv.com", 
        "https://aristeguinoticias.com", 
        "https://www.eluniversal.com.mx/" 
    ]
    
    for site in trusted_sites:
        for keyword in keywords:
            search_url = f"{site}/search?q={keyword}"
            response = requests.get(search_url)
            if response.status_code == 200 and keyword in response.text:
                return True  # Coincidencia encontrada

    return False  # No se encontraron coincidencias

def extract_keywords(text):
    words = text.split()
    keywords = [word for word in words if len(word) > 5]  # Palabras mayores a 5 caracteres
    return keywords[:5]  # Hasta 5 palabras clave

def get_authenticity_probability(authenticity_message, keyword_match, url):
    site = urlparse(url).netloc  # Extraemos el sitio de la URL
    # Incluir la fuente de la URL en el prompt y preguntar si el sitio es verificado
    base_instruction = (
        f"Based on the authenticity message and the source site '{site}', analyze if the source is trustworthy even if it's not a verified site. "
        "Also, is the site verified? Provide a probability from 0 to 1; just return the number."
    )

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a checker providing authenticity probability."},
            {
                "role": "user",
                "content": f"{base_instruction} Authenticity message: {authenticity_message}"
            }
        ]
    )

    probability = completion.choices[0].message.content.strip()
    return probability


if __name__ == "__main__":
    app.run(debug=True)
