import re
import pandas as pd
import plotly.express as px


def get_sentiment_data(df, text_col, analyzer):
    """
    Compute sentiment scores for each text row and append them to a DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame containing text to analyze.
    text_col : str
        Name of the column in `df` that contains text values.
    analyzer : object
        Sentiment analyzer instance with a `polarity_scores(text)` method
        (for example, VADER's `SentimentIntensityAnalyzer`).

    Returns
    -------
    pandas.DataFrame
        A DataFrame with the original columns plus sentiment score columns,
        typically including `neg`, `neu`, `pos`, and `compound`.
    """
    # gather sentiment scores for data frame `df`
    df_sentiment = []

    for review in df[text_col]:
        vs = analyzer.polarity_scores(review)
        df_sentiment.append(vs)

    df_sentiment = pd.DataFrame(df_sentiment,
                                index = df.index)
    df_sentiment = pd.concat((df, df_sentiment), axis=1)

    return df_sentiment


def plot_sentiment(df_sentiment, benchmarks):
    """
    Create an interactive strip plot of sentiment values and benchmark means.

    Parameters
    ----------
    df_sentiment : pandas.DataFrame
        DataFrame containing sentiment columns (`neg`, `neu`, `pos`,
        `compound`) and metadata columns (`name`, `roaster`).
    benchmarks : pandas.DataFrame
        Benchmark statistics indexed by label, where the `'mean'` row
        provides mean sentiment values for plotting reference markers.

    Returns
    -------
    plotly.graph_objects.Figure
        Plotly figure with per-review sentiment strip points and mean
        benchmark markers.
    """
    df_plot = df_sentiment.melt(id_vars=['name', 'roaster'], 
                            value_vars=['neg', 'neu', 'pos', 'compound'],
                            var_name='sentiment_type', value_name='amount')

    fig = px.strip(df_plot, x='sentiment_type', y='amount', 
                template='simple_white', log_y=True,
                hover_name='name',
                hover_data=['roaster'])

    df_ = benchmarks.loc['mean']

    fig.add_scatter(x=df_.index, y=df_, 
                    mode="markers", marker_size=10, marker_color='darkorange', name='review_average')
    
    return fig


def get_sentence_sentiment(text, analyzer):
    """
    Split text into sentences and compute sentiment for each sentence.

    Parameters
    ----------
    text : str
        Input text to split into sentences using `[?.!]` (regex) as
        delimiters.
    analyzer : object
        Sentiment analyzer instance with a `polarity_scores(text)` method.

    Returns
    -------
    pandas.DataFrame
        DataFrame with one row per extracted sentence and appended sentiment
        score columns.
    """
    sentences = re.split('[?.!]', text)
    sentences = [s for s in sentences if s != '']

    df_ = pd.DataFrame(sentences, 
                       columns=['text'])
    
    df_sentiment = get_sentiment_data(df_, 
                                    text_col='text', 
                                    analyzer=analyzer)
    
    return df_sentiment