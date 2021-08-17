#!/usr/bin/env python
# coding: utf-8

import pdfplumber
from bs4 import BeautifulSoup
import requests
import re
import datetime as dt
import pandas as pd
import os

def descargar_pagina(page_number):

    url = 'https://www.unidoscontraelcovid.gob.bo/index.php/category/reportes/page/{}'.format(page_number)
    try:
        response = requests.get(url, timeout=5)
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(e)

def listar_reportes(page, filtro):
    
    reportes = []
    for article in page.select('article'):
        link_nodes = article.select('.col-xs-12.col-md-10 a')
        if len(link_nodes) > 0:
            links = [link['href'] for link in link_nodes if filtro in link['href']]
            reportes.extend(links)
    return reportes

def descargar_reporte(url):

    try:
        reporte_content = requests.get(url, timeout=5).content
        filename = 'reportes/{}'.format(url.split('/')[-1])
        with open(filename, 'wb') as f:
            f.write(reporte_content)
        return filename
    except Exception as e:
        print(e)

def nuevos_reportes(reportes):
    
    descargados = os.listdir('reportes')
    return [reporte for reporte in reportes if reporte.split('/')[-1] not in descargados]

def query_paginas(pdf, query):
    
    for page in pdf.pages:
        content = page.extract_text()
        if content != None:
            if query in ' '.join(content.split()).replace(',','').lower():
                return page

def estandarizar_nombres(variaciones, nombres):
    
    if type(nombres) == list:
        return [variaciones[variacion] for variacion in variaciones.keys() for nombre in nombres if variacion in nombre]
    elif type(nombres) == str:
        return [variaciones[variacion] for variacion in variaciones.keys() if variacion in nombres][0]

def extraer_tabla(page):
    
    columns = []
    index = []
    datos = []
    departamentos = []
    vacuna = 0
    vacunas_variaciones = {'sputnik':'sputnikv', 'sinop':'sinopharm', 'astra':'astrazeneca', 'pfizer':'pfizer', 'john':'janssen', 'jhon':'janssen', 'jans':'janssen'}
    dosis_variaciones = {'1':'primera', '2':'segunda', 'nica':'única'}

    filas = page.extract_table()
    vacunas = ['_'.join(campo.lower().split()) for campo in filas[0] if type(campo) == str and campo.lower() not in ['departamento', 'total ambas', None]]
    vacunas = estandarizar_nombres(vacunas_variaciones, vacunas)
    
    for i, campo in enumerate(filas[1]):
        if type(campo) == str:
            if 'dosis' in campo.lower() and 'total' not in campo.lower():
                tipo_dosis = estandarizar_nombres(dosis_variaciones, campo.lower())
                columns.append('{}_{}'.format(vacunas[vacuna], tipo_dosis))
                index.append(i)
            elif campo.lower() == 'total':
                vacuna += 1
    for fila in filas[2:-1]:
        datos.append([fila[i] for i in index])
        departamentos.append(fila[0].lower())

    df = pd.DataFrame(datos, columns=columns, index=departamentos)
    return df[sorted(df.columns)]

def que_fecha(pdf):
    
    match = re.findall('[0-9]{1,2}\/[0-9]{1,2}/[0-9]{4}', pdf.pages[0].extract_text())
    return dt.datetime.strptime(match[0], '%d/%m/%Y')

def consolidar(df):

    for departamento, fila in df.iterrows():
        fila = pd.DataFrame(fila).T
        fila.index = [date]
        csv_file = 'dosis_por_proveedor/{}.csv'.format(departamento.replace(' ', '_'))
        df2 = pd.concat([pd.read_csv(csv_file, parse_dates=[0], index_col=[0]), fila]).fillna(0).astype(int)
        df2 = df2[~df2.index.duplicated(keep='last')]
        df2.sort_index().to_csv(csv_file)

def extraer_barras(page):
    
    valores = page.within_bbox((.12 * float(page.width), 0.1 * float(page.height), .9 * float(page.width), .75 * float(page.height))).extract_words()
    return pd.DataFrame([pd.DataFrame(valores).sort_values('x0').text.apply(lambda x: float(x.replace('%', '')) / 100).tolist()], columns=['18 a 29', '30 a 39', '40 a 49', '50 a 59', '60 y más', 'Bolivia'], index=[date])

def cobertura(pdf, query, csv_file):
    
    page = query_paginas(pdf, query)
    if page:
        barras = extraer_barras(page)
        csv_df = pd.read_csv(csv_file, parse_dates=[0], index_col=0)
        csv_df = pd.concat([csv_df, barras])
        csv_df = csv_df[~csv_df.index.duplicated(keep='last')]
        csv_df.sort_index().to_csv(csv_file)
        
# ----------------------------
    
# Consultar la página web
website = descargar_pagina(1)
# Si la página está disponible
if website is not None:
    # Listar reportes que mencionan `vacuna` en el enlace
    reportes = listar_reportes(website, 'vacuna')
    # Para cada nuevo reporte
    for reporte in nuevos_reportes(reportes):
        # Descargar el reporte
        filename = descargar_reporte(reporte)
        # Si el reporte está disponible
        if filename is not None:
            # Abrirlo
            pdf = pdfplumber.open(filename)
            # De qué fecha es
            date = que_fecha(pdf)
            # En qué página está la tabla que me interesa
            page = query_paginas(pdf, 'cantidad de dosis de la vacuna covid-19 aplicadas según proveedor')
            # Extraer la tabla
            df = extraer_tabla(page)
            # Guardarla
            consolidar(df)
            # Extraer y consolidar coberturas por población y tipo de dosis
            cobertura(pdf, 'cobertura de población vacunada con 1ra dosis según', 'cobertura/por_edad_primera_dosis.csv')
            cobertura(pdf, 'cobertura de población vacunada con esquema completo', 'cobertura/por_edad_esquema_completo.csv')
