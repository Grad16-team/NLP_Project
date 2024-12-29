# -*- coding: utf-8 -*-
"""GaussianNaiveBayes_LSTM.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Ij_0HrtZ3BoDilZP5-6UxBCku2vVtBRJ
"""

!pip install sentence_transformers
!pip install bitsandbytes

"""# 1) Data Loading & Pre-processing"""

import pandas as pd
df = pd.read_excel("/content/Main.xlsx")

df.head()

df.columns

df = df.drop(columns=['Annotator ID', 'Text','Batch', 'ID', 'Comments', 'Type', 'Source Language', 'English MT',"Type of Bias","Propaganda","Type of Propaganda"], errors='ignore')

df.head()

total_rows = len(df)
print(f"Total number of rows: {total_rows}")

df.isna().sum()

import numpy as np

df.replace(['', 'None', 'nan'], np.nan, inplace=True)
df.dropna(subset=['Bias'], inplace=True)

df.isna().sum()

df.head()

total_rows = len(df)
print(f"Total number of rows: {total_rows}")

print(df['Bias'].cat.categories if df['Bias'].dtype.name == 'category' else df['Bias'].unique())

columns_to_check = ['Bias']

for column in columns_to_check:
    print(f"Class counts for '{column}':")
    print(df[column].value_counts())
    print("\n")

!pip install emoji

import re
import emoji

def preprocess_text(text):
    # Ensure text is a string
    text = str(text)

    # 1. Remove hashtags
    text = re.sub(r'#\w+', '', text)

    # 2. Remove full URLs with protocols (e.g., "http://example.com")
    text = re.sub(r'https?://\S+|www\.\S+|bit\.ly\S*', '', text)

    # 3. Remove standalone paths without protocols (e.g., "/content/kan-news/defense/629514/")
    text = re.sub(r'/\S+', '', text)

    # 4. Remove emails
    text = re.sub(r'\S+@\S+', '', text)

    # 5. Remove emojis
    text = emoji.replace_emoji(text, replace='')

    # 6. Remove diacritics
    arabic_diacritics = re.compile(r'[\u0617-\u061A\u064B-\u0652]')
    text = re.sub(arabic_diacritics, '', text)

    # 7. Remove Tatweel (ـ)
    text = re.sub(r'ـ', '', text)

    # 8. Normalize Arabic text
    text = re.sub(r'[إأآا]', 'ا', text)  # Unify Alif variants
    text = re.sub(r'ة', 'ه', text)  # Replace Taa Marbuta with Haa
    text = re.sub(r'ى', 'ي', text)  # Replace Alef Maqsura with Ya

    # 9. Remove repeated characters (e.g., "ممتتتاز" → "ممتاز")
    text = re.sub(r'(.)\1+', r'\1', text)

    # Return cleaned text
    return text

# Apply the preprocessing function
df['Arabic MT'] = df['Arabic MT'].apply(preprocess_text)

df['Arabic MT'][9022]

"""# Handling imbalanced dataset"""

from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import BorderlineSMOTE
import numpy as np

model = SentenceTransformer("intfloat/multilingual-e5-large")

X = df['Arabic MT']
y = df['Bias']

X_embeddings = model.encode(X.tolist(), convert_to_numpy=True)

X_train, X_test, y_train, y_test = train_test_split(X_embeddings, y, test_size=0.2, stratify=y, random_state=42)

from imblearn.over_sampling import BorderlineSMOTE

borderline_smote = BorderlineSMOTE(random_state=42)
X_train_resampled, y_train_resampled = borderline_smote.fit_resample(X_train, y_train)

print("Class distribution after Borderline-SMOTE:")
print(pd.Series(y_train_resampled).value_counts())

from sklearn.metrics.pairwise import cosine_similarity

original_embeddings = X_train
synthetic_embeddings = X_train_resampled[len(X_train):]

cos_sim = cosine_similarity(original_embeddings, synthetic_embeddings)
average_similarity = np.mean(np.max(cos_sim, axis=0))
print(f"Average Cosine Similarity of Synthetic Samples: {average_similarity:.4f}")

if average_similarity < 0.7:
    print("Warning: Synthetic samples are significantly different from the original data.")
else:
    print("Synthetic samples appear similar to the original data.")

from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import classification_report, confusion_matrix

# Split the training data into training and validation sets
X_train_final, X_val, y_train_final, y_val = train_test_split(X_train_resampled, y_train_resampled, test_size=0.2, random_state=42)

# Initialize and train the Naive Bayes model
nb_model = GaussianNB()
nb_model.fit(X_train_final, y_train_final)
y_pred = nb_model.predict(X_val)

# Print the classification report and confusion matrix
print("Classification Report:")
print(classification_report(y_val, y_pred))

print("Confusion Matrix:")
print(confusion_matrix(y_val, y_pred))

X_train_resampled, X_val, y_train_resampled, y_val = train_test_split(X_train_resampled, y_train_resampled, test_size=0.2, random_state=42)

# Now reshape as needed for LSTM
X_train_final = X_train_resampled.reshape((X_train_resampled.shape[0], 1, X_train_resampled.shape[1]))
X_val = X_val.reshape((X_val.shape[0], 1, X_val.shape[1]))

from sklearn.preprocessing import OneHotEncoder
one_hot_encoder = OneHotEncoder()
y_train_final = one_hot_encoder.fit_transform(y_train_resampled.reshape(-1, 1)).toarray()
y_val_onehot = one_hot_encoder.transform(y_val.reshape(-1, 1)).toarray()

# Print the shapes to verify
print("y_train_final shape:", y_train_final.shape)
print("y_val_onehot shape:", y_val_onehot.shape)

from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout
def create_lstm_model(optimizer='adam', dropout_rate=0.2):
    num_classes = y_train_final.shape[1]

    model = Sequential([
        LSTM(64, input_shape=(X_train_final.shape[1], X_train_final.shape[2]), return_sequences=False),
        Dropout(dropout_rate),
        Dense(64, activation='relu'),
        Dense(num_classes, activation='softmax')
    ])

    model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])
    return model

model = create_lstm_model()
model.fit(X_train_final, y_train_final, epochs=10, batch_size=32, validation_data=(X_val, y_val_onehot))

# Evaluate the model
loss, accuracy = model.evaluate(X_val, y_val_onehot)
print(f"Validation Loss: {loss}")
print(f"Validation Accuracy: {accuracy}")

