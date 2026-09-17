import pickle
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from utils.modeling import *


def get_coffee_data():
    # this is just the original data from Kaggle
    df_coffee = pd.read_csv("https://raw.githubusercontent.com/leontoddjohnson/datasets/refs/heads/main/data/coffee_analysis.csv")

    df_coffee.drop_duplicates(subset='desc_1', 
                              inplace=True)

    df_coffee.dropna(subset=['desc_1', 
                            'roast', 
                            'loc_country'], 
                    inplace=True)
    
    return df_coffee


if __name__ == '__main__':
    # ------------------------------------------------------
    #                       GET DATA
    # ------------------------------------------------------
    df_coffee = get_coffee_data()

    # ------------------------------------------------------
    #                    "TRAIN" MODEL
    # ------------------------------------------------------
    analyzer = SentimentIntensityAnalyzer()

    # Note: this is a simple model which doesn't require data to train
    with open('./model.pickle', 'wb') as f:
        pickle.dump(analyzer, f)

    # ------------------------------------------------------
    #               CALCULATE SENTIMENT DATA
    # ------------------------------------------------------
    df_sentiment = get_sentiment_data(df_coffee, 'desc_1', analyzer)

    # ignored by git, but uploaded to Google Sheets
    df_sentiment.to_csv('./data/coffee_analysis.csv', index=False)

    