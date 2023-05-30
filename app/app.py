# Basically the requests package is the one that is able to pull in json data
import os
import re
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import spacy
from nltk.stem.porter import *
import gensim
from serpapi import GoogleSearch

# 4. Aggregation

# Spacy lemmatizer | basically this cuts the words
# Load core model
sp = spacy.load('en_core_web_sm')
# Remove stopwords
all_stopwords = sp.Defaults.stop_words
jk_api_key = os.getenv('JK_API_KEY')


# 1. Function to find the job descriptions of the listed job
def get_jobs(start, job_title):
    # Create an empty dataframe
    job_data = pd.DataFrame()

    for num in start:
        params = {
            "engine": "google_jobs",
            "google_domain": "google.com",
            "q": f"{job_title}",
            "gl": "us",
            "hl": "en",
            "chips": "date_posted;week",
            # todo: does it make sense to user information from a user?
            "location": "New York, New York, United States",
            "api_key": jk_api_key,
            "start": f"{num}"
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        # Put results into dataframe
        jobs = pd.DataFrame.from_dict(results['jobs_results'])
        # Append values to dataframe
        job_data = pd.concat([jobs, job_data], ignore_index=True)

    return job_data


# 2. With the job data in hand, extract the relevant job descriptions
def clean_jobs(job_data):
    # Find only the bullet points
    descriptions = []
    for i, _ in enumerate(job_data.description):
        # Check that the job description is in string format
        if isinstance(job_data.description[i], str) is True:
            st = ' '.join(map(str, re.findall('•(.+)', job_data.description[i])))
            descriptions.append(st)
        else:
            st = ''
            descriptions.append(st)

    job_data["descriptions_string"] = descriptions
    # Make all the text lower case
    job_data["descriptions_string"] = job_data["descriptions_string"].str.lower()

    return job_data["descriptions_string"]


def lemmatize_words(job_description):
    result = []
    # tokenize the sentence
    document = sp(job_description)
    for word in document:
        if not word.is_punct and not word.like_num and not word.is_stop and not word.is_space and (
                word.pos_ in ('NOUN', 'PROPN', 'VERB')) and word.lemma_ != 'datum':
            result.append(word.lemma_.lower())

    result = [word for word in result if not word in all_stopwords]  # Don't want this to be unique

    return result


# 3. Clean the text, prepare it for the words counts
def text_process(job_descriptions):
    lemmatize_docs = []

    for doc in job_descriptions:
        lemmatize_docs.append(lemmatize_words(doc))

    return lemmatize_docs


# 4. Find skills: With the job data, lemmatize and find the find_skills
def find_skills(lemmatize_docs):
    dictionary = gensim.corpora.Dictionary(lemmatize_docs)  # Create dictionary of all tokens
    bow_corpus = [dictionary.doc2bow(doc, allow_update=True) for doc in
                  lemmatize_docs]  # Run a BoW for each tokenized job description
    id_words = [[(dictionary[id_word], count) for id_word, count in line] for line in
                bow_corpus]  # Convert id to the actual words
    flat_list = [item for sublist in id_words for item in sublist]  # Put all the list together
    combined_list = list(
        Counter(key for key, num in flat_list for idx in range(num)).items())  # Aggregate the value across all lists
    skills = pd.DataFrame(combined_list, columns=['word', 'occurrences']).sort_values(by=['occurrences'],
                                                                                      ascending=False,
                                                                                      ignore_index=True)

    return skills


# 5. Visualize the data
def visualize(skills, project_id, bucket_name, gcs_file_name):
    # Set the plot dimensions
    a4_dims = (20, 9)
    fig, ax = plt.subplots(figsize=a4_dims)
    fig.set_layout_engine('compressed')

    sns.set_theme(style="whitegrid")
    sns.set(font_scale=1.4)

    keys = list(skills.word[:15])
    vals = list(skills.occurrences[:15])
    pal = sns.color_palette("mako", len(vals))

    ax.set(xlabel='Skill', ylabel='# of Job Descriptions')
    ax.set_xticklabels(keys, rotation=30)
    ax = sns.barplot(x=keys, y=vals, palette=pal)

    # Save the plot to a buffer
    # buf = BytesIO()
    plt.savefig(gcs_file_name, format='png', dpi=300, transparent=True)

    return gcs_file_name
