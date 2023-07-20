from flask import Flask, request
from run_ner import get_ner
from run_pos import get_pos

# print(get_pos('Kepala Dinas Pariwisata dan Ekonomi Kreatif Andhika Permata menyinggung soal pertemuan aktivis lesbian, gay, biseksual, dan transgender (LGBT) yang semula direncanakan akan digelar di Jakarta. Dia menegaskan Disparekraf DKI menolak keberadaan mereka sebab tidak sesuai dengan budaya Indonesia. \nHal itu disampaikan Andhika saat rapat bersama Komisi B DPRD DKI Jakarta soal perkembangan ekonomi Jakarta, Rabu (12/7/2023). Andhika mengungkapkan Disparekraf DKI senang jika ada wisatawan asing ke Jakarta tapi tidak dengan komunitas LGBT.'))

app = Flask(__name__)

@app.route('/ner', methods=["POST"])
def ner():
    entities = get_ner(request.form['text'])
    return {
        'entities': entities
    }

@app.route('/pos', methods=["POST"])
def pos():
    tags = get_pos(request.form['text'])
    return {
        'tags': tags
    }