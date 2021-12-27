
from os import write
import time
import pandas as pd
import base64
from typing import Sequence
import streamlit as st
from sklearn.metrics import classification_report


from models import create_nest_sentences, load_summary_model, summarizer_gen, load_model, classifier_zero
from utils import plot_result, plot_dual_bar_chart, examples_load, example_long_text_load
import json

ex_text, ex_license, ex_labels, ex_glabels = examples_load()
ex_long_text = example_long_text_load()


# if __name__ == '__main__':
st.header("Summzarization & Multi-label Classification for Long Text")
st.write("This app summarizes and then classifies your long text with multiple labels.")
st.write("__Inputs__: User enters their own custom text and labels.")
st.write("__Outputs__: A summary of the text, likelihood percentages for each label and a downloadable csv of the results. \
    Option to evaluate results against a list of ground truth labels, if available.")

with st.form(key='my_form'):
    example_text = ex_long_text #ex_text
    display_text = "[Excerpt from Project Gutenberg: Frankenstein]\n" + example_text + "\n\n" + ex_license
    text_input = st.text_area("Input any text you want to summarize & classify here (keep in mind very long text will take a while to process):", display_text)

    if text_input == display_text:
        text_input = example_text

    labels = st.text_input('Enter possible labels (comma-separated):',ex_labels, max_chars=1000)
    labels = list(set([x.strip() for x in labels.strip().split(',') if len(x.strip()) > 0]))
    
    glabels = st.text_input('If available, enter ground truth labels to evaluate results, otherwise leave blank (comma-separated):',ex_glabels, max_chars=1000)
    glabels = list(set([x.strip() for x in glabels.strip().split(',') if len(x.strip()) > 0]))

    threshold_value = st.slider(
         'Select a threshold cutoff for matching percentage (used for ground truth label evaluation)',
         0.0, 1.0, (0.5))

    submit_button = st.form_submit_button(label='Submit')


with st.spinner('Loading pretrained summarizer mnli model...'):
    start = time.time()
    summarizer = load_summary_model()   
    st.success(f'Time taken to load summarizer mnli model: {round(time.time() - start,4)} seconds')

with st.spinner('Loading pretrained classifier mnli model...'):
    start = time.time()
    classifier = load_model()    
    st.success(f'Time taken to load classifier mnli model: {round(time.time() - start,4)} seconds')


if submit_button:
    if len(labels) == 0:
        st.write('Enter some text and at least one possible topic to see predictions.')
    
    with st.spinner('Generating summaries and matching labels...'):
        my_expander = st.expander(label='Expand to see summary generation details')
            with my_expander:
            # For each body of text, create text chunks of a certain token size required for the transformer
            nested_sentences = create_nest_sentences(document = text_input, token_max_length = 1024)

            summary = []
            # st.markdown("### Text Chunk & Summaries")
            st.markdown("_Breaks up the original text into sections with complete sentences totaling \
                less than 1024 tokens, a requirement for the summarizer._")

            # For each chunk of sentences (within the token max), generate a summary
            for n in range(0, len(nested_sentences)):
                text_chunk = " ".join(map(str, nested_sentences[n]))
                st.markdown(f"###### Original Text Chunk {n+1}/{len(nested_sentences)}" )
                st.markdown(text_chunk)

                chunk_summary = summarizer_gen(summarizer, sequence=text_chunk, maximum_tokens = 300, minimum_tokens = 20)
                summary.append(chunk_summary) 
                st.markdown(f"###### Partial Summary {n+1}/{len(nested_sentences)}")
                st.markdown(chunk_summary)
                # Combine all the summaries into a list and compress into one document, again
                final_summary = " \n\n".join(list(summary))

        # final_summary = summarizer_gen(summarizer, sequence=text_input, maximum_tokens = 30, minimum_tokens = 100)
        st.markdown("### Combined Summary")
        st.markdown(final_summary)
    

        st.markdown("### Top Label Predictions on Summary & Full Text")
        with st.spinner('Matching labels...'):
            topics, scores = classifier_zero(classifier, sequence=final_summary, labels=labels, multi_class=True)
            # st.markdown("### Top Label Predictions: Combined Summary")
            # plot_result(topics[::-1][:], scores[::-1][:])
            # st.markdown("### Download Data")
            data = pd.DataFrame({'label': topics, 'scores_from_summary': scores})
            # st.dataframe(data)
            # coded_data = base64.b64encode(data.to_csv(index = False). encode ()).decode()
            # st.markdown(
            #     f'<a href="data:file/csv;base64, {coded_data}" download = "data.csv">Download Data</a>',
            #     unsafe_allow_html = True
            #     )

            topics_ex_text, scores_ex_text = classifier_zero(classifier, sequence=example_text, labels=labels, multi_class=True)
            plot_dual_bar_chart(topics, scores, topics_ex_text, scores_ex_text)

            data_ex_text = pd.DataFrame({'label': topics_ex_text, 'scores_from_full_text': scores_ex_text})
            
            data2 = pd.merge(data, data_ex_text, on = ['label'])

            if len(glabels) > 0:
                gdata = pd.DataFrame({'label': glabels})
                gdata['is_true_label'] = int(1)           
            
                data2 = pd.merge(data2, gdata, how = 'left', on = ['label'])
                data2['is_true_label'].fillna(0, inplace = True)

            st.markdown("### Data Table")
            with st.spinner('Generating a table of results and a download link...'):
                st.dataframe(data2)

                @st.cache
                def convert_df(df):
                     # IMPORTANT: Cache the conversion to prevent computation on every rerun
                     return df.to_csv().encode('utf-8')
                csv = convert_df(data2)
                st.download_button(
                     label="Download data as CSV",
                     data=csv,
                     file_name='text_labels.csv',
                     mime='text/csv',
                 )
                # coded_data = base64.b64encode(data2.to_csv(index = False). encode ()).decode()
                # st.markdown(
                #     f'<a href="data:file/csv;base64, {coded_data}" download = "data.csv">Click here to download the data</a>',
                #     unsafe_allow_html = True
                #     )

            if len(glabels) > 0:
                st.markdown("### Evaluation Metrics")
                with st.spinner('Evaluating output against ground truth...'):

                    section_header_description = ['Summary Label Performance', 'Original Full Text Label Performance']
                    data_headers = ['scores_from_summary', 'scores_from_full_text']
                    for i in range(0,2):
                        st.markdown(f"##### {section_header_description[i]}")
                        report = classification_report(y_true = data2[['is_true_label']], 
                            y_pred = (data2[[data_headers[i]]] >= threshold_value) * 1.0,
                            output_dict=True)
                        df_report = pd.DataFrame(report).transpose()
                        st.markdown(f"Threshold set for: {threshold_value}")
                        st.dataframe(df_report)

            st.success('All done!')
            st.balloons()
