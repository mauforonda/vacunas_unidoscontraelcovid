#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import os

def parse_mauforondavacunas():
    "Transformar los datos de mauforonda/vacunas a una tabla de 4 columnas: fecha, tipo, departamento y dosis"
    
    return pd.concat(
            [pd.read_csv('consolidado/mauforonda_vacunas/{}.csv'.format(tipo), parse_dates=['fecha'], index_col=['fecha'])
             .drop(columns=['Total'])
             .stack()
             .reset_index()
             .assign(tipo=tipo)
             .rename(columns={'level_1':'departamento', 0:'dosis'}) 
             for tipo in ['primera', 'segunda']]).sort_values(['fecha', 'tipo', 'departamento'])

def parse_departamento(departamento_filename):
    "Transformar los datos de un departamento en mauforonda/unidoscontraelcovid a una tabla de 4 columnas: fecha, tipo, departamento y dosis"
    
    df = pd.read_csv('dosis_por_proveedor/{}'.format(departamento_filename), parse_dates=[0], index_col=[0])
    return pd.concat(
            [pd.DataFrame(
                df[[col for col in df.columns if tipo in col]]
                .sum(axis=1))
             .assign(departamento=departamento_filename.split('.')[0].replace('_',' ').title())
             .assign(tipo=tipo)
             .reset_index()
             .rename(columns={0:'dosis', 'index':'fecha'}) for tipo in ['primera', 'segunda', 'única']])

def parse_unidoscontraelcovid():
    "Transformar los datos de todos los departamentos en mauforonda/unidoscontraelcovid"

    return pd.concat([parse_departamento(departamento_filename) for departamento_filename in os.listdir('dosis_por_proveedor/')]).sort_values(['fecha', 'tipo', 'departamento'])

def consolidar():
    "Unir todos los datos, preservar los datos de unidoscontraelcovid en caso de días duplicados y producir un csv"
    
    mauforondavacunas = parse_mauforondavacunas()
    unidoscontraelcovid = parse_unidoscontraelcovid()
    df = pd.concat([mauforondavacunas, unidoscontraelcovid]).drop_duplicates(['fecha', 'departamento', 'tipo'], keep='last').sort_values(['fecha', 'tipo', 'departamento'])
    df[['fecha', 'tipo', 'departamento', 'dosis']].to_csv('consolidado/vacunas.csv', float_format="%.0f", index=False)

consolidar()
