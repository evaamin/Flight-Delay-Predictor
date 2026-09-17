# a simple streamlit app

Treat this repository as a template for your own data- and model-driven Streamlit app.

## Prerequisites

This tutorial assumes the following:

- You have a GitHub account, and you're familiar with using git and .gitignore files.
- You can build and manage a pip Python environment.
- You are at least familiar with environment variables.

## Project Setup

> Download [this data](https://www.kaggle.com/datasets/schmoyote/coffee-reviews-dataset/) (i.e., the coffee_analysis.csv file) for this web app. Refer to the *train_model.py* file to see where this gets used.

1. Create a new folder for your web app (give it an [appropriate](https://gravitydept.com/blog/devising-a-git-repository-naming-convention) name), and place it with your other Git projects.
2. Initiate a Git repository in this folder with `git init`. Use Git early and often to ensure that your changes are tracked, and you can always go back to (or compare with) a past version that works.
   - Note the contents of the .gitignore file. **"Secret files" (e.g., a .env file) and data (e.g., .csv files) should be strictly ignored.**
3. Initialize a pip environment using the *env.yml* file in this directory. For example, if you're using Ana/Miniconda, you'll use `conda env create -f env.yml`.
   - The use of "env.yml" instead of "environment.yml" is intentional. If you prefer to use "environment.yml", you may want to add the file to your .gitignore list (see the note below).
4. Any time you add new packages to the environment, **update the .yml file**, and save an updated requirements file with `pip list --format=freeze > requirements.txt` (this should be run **within the environment**, so you'll need to activate it first).
   - **All packages should be installed using pip.**
   - *Note:You may have seen direction to use `pip freeze ...`, but when we use pip "in" conda as we are here, we need [this adjustment](https://stackoverflow.com/a/62872764).*

**Note:** [Streamlit will only use \*one dependency file](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/app-dependencies#other-python-package-managers). If you have both a "requirements.txt" file *and* an "environment.yml" file in your repository, you will likely run into issues. The recommended option is to keep the *requirements.txt* file tracked on GitHub and the "environment.yml" file ignored (and unseen by Streamlit Cloud).

## Modularizing Code

Consider creating a *scratch.ipynb* file for testing out code as you build your web app, and make sure to add it to your *.gitignore* file.

When you feel ready for it, consider dividing your code into separate Python files, saved in modular folders. For example, you'll notice in this repository, there is a *utils* folder. In that folder, we have a few Python files with code tested out in Jupyter first. Once it was determined the code worked in Jupyter, it was transferred into the separate Python file.

This *utils* folder, [including the empty *\_\_init__.py* file](https://stackoverflow.com/a/48804718), creates a Python [package](https://docs.python.org/3/tutorial/modules.html#packages) of multiple modules. For instance, if you open a "scratch" notebook from the directory containing this folder, you'll find you can run code like `from utils.modeling import clean_data`. This keeps your notebook(s) clean, and it makes debugging much easier. While you're working on your code, use the [autoreload functionality](https://ipython.org/ipython-doc/3/config/extensions/autoreload.html) to update code as you go.

## Model Training

### Data

The raw data for this tutorial comes from [Kaggle](https://www.kaggle.com/datasets/schmoyote/coffee-reviews-dataset/) (it can also be downloaded [here](https://raw.githubusercontent.com/leontoddjohnson/datasets/refs/heads/main/data/coffee_analysis.csv)). It is prepared for the web app in the *train_model.py* file. Once the data is prepared for the web app, it should be saved somewhere the app can access it, even if it's run on the cloud. **Data should not be stored on GitHub**, so we use Google Sheets with one of the following methods:

- **[Google Sheets integration with Streamlit](https://docs.streamlit.io/develop/tutorials/databases/public-gsheet)**

- Accessing a **published Google Sheet**:

  - Open your Google Sheets document.

  - Go to `File > Share > Publish to web`. Choose the sheet you want to publish and publish it as "Comma-separated values (.csv)".

  - Select "Automatically republish when changes are made" (this may be in a dropdown menu in the popup).

  - Get the CSV link. It should look something like this:
    
      `https://docs.google.com/spreadsheets/d/e/{spreadsheet_id}/pub?...output=csv`

**In either case, the URL should be saved as a Streamlit secret (see below).**

### Sentiment Analysis

The model for this web app did not require any data to "train". Instead, it just needs to be instantiated and saved as a model.pickle file. All this is done in the train_model.py file, namely because the model itself is used to prepare data for the web app (see the `df_sentiment` dataframe).

Typically, models should also be saved in some cloud storage location, but for our purposes, saving the model to the GitHub repository is okay (especially because it is not very big).

## Streamlit

The app in this repository is run on [Streamlit](https://streamlit.io/).

Code can be tested locally with `streamlit run app.py` (assuming your app file name is `app.py`, of course). Once the app is running as you like, you can click the "Deploy" button on the upper right of the page. If you haven't already, you may need to [set up a Streamlit Cloud account](https://docs.streamlit.io/streamlit-community-cloud/get-started) to link your project GitHub repository.

*Note: before you deploy your app, make sure to create your "requirements.txt" file (see above).*

#### Secrets

We use the [secrets.toml](https://docs.streamlit.io/develop/api-reference/connections/secrets.toml) file to manage environment variables used in this web app. This gives us a level of control over the security of API keys, passwords, etc., as environment variables.

Once your environment variables are working locally, make sure you configure them accordingly on Streamlit Cloud using their [Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management).

**Make sure ".streamlit" is added to your [.gitignore file](https://www.atlassian.com/git/tutorials/saving-changes/gitignore)**.

#### Caching

This app uses [Streamlit caching](https://docs.streamlit.io/library/advanced-features/caching) capabilities to cache (or save) objects whose loading would otherwise slow down the application. To do so, the app employs decorator functions. For more information on decorator functions in Python, I recommend the first two sections of [this article on RealPython](https://realpython.com/primer-on-python-decorators), by Geir Arne Hjelle.

In short, a decorator function adjusts its companion function by "wrapping" it in some other function. Here, the `@st.cache_data` or `@st.cache_object` decorator wraps its companion function such that the input is checked against a list of previous inputs of that function. If it's been run before, the output is pulled from the cache instead of running the routine all over again (e.g., see the `filter_coffee` function in the preprocessing.py file).

## Other Resources

- You may consider using [Google Colab](https://colab.research.google.com/) to train your model and mold your project. Feel free to [use this as a template](https://colab.research.google.com/drive/1kgr3zMrC4sgBZXCx0jgVwXAIPXJgUJn_?usp=sharing) (i.e., make a copy of that notebook if you like). 
- Note that this app just uses the native Streamlit visualization functionality. For more flexibility on your visualization options, see [here](https://docs.streamlit.io/library/api-reference/charts).
- [Render](https://render.com/) and [Railway](https://railway.app/) are alternatives for hosting more robust web apps, but their setup can get complex. Also, their free tiers can be a bit restricting, so it's often best to just pay their monthly fee.
- [Plotly Dash](https://dash.plotly.com/tutorial) is an alternative for building extensive interactive visualizations, dashboards, and more intriguing Python-based products. It requires a more robust app hosting resource like Render or Railway, and it does have a bit of a steeper learning curve.