# Basically the requests package is the one that is able to pull in json data
import requests
from flask import Flask
import pandas as pd
import os

# 1. The API to pull job descriptions
from serpapi import GoogleSearch

# 3. Start comparing the topics together
# Import our language packages
import re
import gensim
import nltk
import spacy
import en_core_web_sm

from gensim.utils import simple_preprocess
from gensim.parsing.preprocessing import STOPWORDS
from nltk.stem import WordNetLemmatizer, SnowballStemmer
from nltk.stem.porter import *
from collections import Counter

# 4. Aggregation
import operator

# 5. Visualization
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from io import BytesIO
import base64
from google.cloud import storage

# Define the pagination
start = [0,10,20,30]

# 1. Function to find the job descriptions of the listed job
def get_jobs(start, job_title):
  #Create an empty dataframe
  job_data = pd.DataFrame()
  
  for i in start:
      num = i
      params = {
      "engine": "google_jobs",
      "google_domain": "google.com",
      "q": f"{job_title}",
      "gl": "us",
      "hl": "en",
      "chips": "date_posted;week",
      "location": "New York, New York, United States",
      "api_key": "7f3d37b4a589aee85970bb04f3ba143116a340b8d706b786d0f96827c43ae5ab",
      "start":f"{num}"
      }
      search = GoogleSearch(params)
      results = search.get_dict()

      # Put results into dataframe
      jobs = pd.DataFrame.from_dict(results['jobs_results'])
      # Append values to dataframe
      job_data = pd.concat([jobs, job_data],ignore_index=True)
    
  return job_data

# 2. With the job data in hand, extract the relevant job descriptions
def clean_jobs(job_data):
    # Find only the bullet points
    descriptions = []
    for i, _ in enumerate(job_data.description):
      # Check that the job description is in string format
      if isinstance(job_data.description[i], str) is True:
        st = ' '.join(map(str, re.findall('•(.+)',job_data.description[i])))
        descriptions.append(st)
      else:
        st = ''
        descriptions.append(st)
    
    job_data["descriptions_string"] = descriptions
    # Make all the text lower case
    job_data["descriptions_string"] = job_data["descriptions_string"].str.lower()

    return job_data["descriptions_string"]

# Spacy lemmatizer | basically this cuts the words
# Load core model
sp = spacy.load('en_core_web_sm')
# Remove stopwords
all_stopwords = sp.Defaults.stop_words

def lemmatize_words(job_description):
  result = []
  # tokenize the sentence
  document = sp(job_description)
  for word in document:
    if not word.is_punct and not word.like_num and not word.is_stop and not word.is_space and (word.pos_ in ('NOUN','PROPN','VERB')) and word.lemma_ !='datum':
      result.append(word.lemma_.lower())

  result = [word for word in result if not word in all_stopwords] # Don't want this to be unique
  
  return result

# 3. Clean the text, prepare it for the words counts
def text_process(job_descriptions): 
    lemmatize_docs = []

    for doc in job_descriptions:
        lemmatize_docs.append(lemmatize_words(doc))
    
    return lemmatize_docs

# 4. Find skills: With the job data, lemmatize and find the find_skills
def find_skills(lemmatize_docs):
  dictionary= gensim.corpora.Dictionary(lemmatize_docs) # Create dictionary of all tokens
  bow_corpus = [dictionary.doc2bow(doc, allow_update=True) for doc in lemmatize_docs] # Run a BoW for each tokenized job description
  id_words = [[(dictionary[id], count) for id, count in line] for line in bow_corpus] # Convert id to the actual words
  flat_list = [item for sublist in id_words for item in sublist] # Put all the list together
  combined_list = list(Counter(key for key, num in flat_list for idx in range(num)).items()) # Aggregate the value across all lists
  skills = pd.DataFrame(combined_list, columns=['word', 'occurences']).sort_values(by=['occurences'], ascending=False, ignore_index=True)

  return skills

# 5. Visualize the data
def visualize(skills,project_id, bucket_name, gcs_file_name):
  # Set the plot dimensions
  a4_dims = (20, 9)
  fig, ax = plt.subplots(figsize=a4_dims)
  
  sns.set_theme(style="whitegrid")
  sns.set(font_scale=1.4)

  keys = list(skills.word[:15])
  vals = list(skills.occurences[:15])
  pal = sns.color_palette("mako", len(vals))

  ax.set(xlabel='Skill', ylabel='# of Job Descriptions')
  ax.set_xticklabels(keys,rotation=30)
  ax = sns.barplot(x=keys, y=vals, palette=pal)

  plt.title('The most frequently mentioned nouns and verbs in job descriptions')
  # Save the plot to a buffer
  buf = BytesIO()
  plt.savefig(buf, format='png',dpi=300,transparent=True)

  # Create a client for interacting with Google Cloud Storage
  storage_client = storage.Client(project=project_id)
  
  # Get a reference to the desired bucket
  bucket = storage_client.get_bucket(bucket_name)
  
  # Create a new blob object representing the image file
  blob = bucket.blob(gcs_file_name)
  
  # Upload the image data to Google Cloud Storage
  blob.upload_from_string(buf.getvalue(), content_type='image/png')

  # Return the public URL of the image
  return blob.public_url

def get_skills(request):

  # This is the information sent from the request
  content_type = request.headers['content-type']
  
  if content_type == 'application/json':
      request_json = request.get_json(silent=True)
      if request_json and 'name' in request_json:
          job = request_json['name']
  
  # Set your Google Cloud Storage project ID
  project_id = "job-selector"

  # Set the name of the bucket where you want to upload the image
  bucket_name = "job_images_bucket"

  # Set the name you want to give the image in Google Cloud Storage
  gcs_file_name = f"{job}.png"
  
  # Get the skills
  job_data = get_jobs(start, job) # Get the jobs
  job_descriptions = clean_jobs(job_data) # Clean the job description
  clean_texts = text_process(job_descriptions) # Clean the job description text
  skills = find_skills(clean_texts) # Aggregates the words
  chart = visualize(skills,project_id, bucket_name, gcs_file_name) # Visualizes the text and creates a URL
  
  return chart
