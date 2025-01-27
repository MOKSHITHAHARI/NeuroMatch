# -*- coding: utf-8 -*-
"""ADHD_CNN_snn_triplet.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ogKL42lFP6e-atf0-Uy5SDbX_udV1t5l

Importing Libraries
"""

import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split

"""Folder Paths"""

adhd_folder = "/content/ADHD_MI"
control_folder = "/content/CONTROL_MI"

"""Function to load data from folder"""

def load_data_from_folder(folder_path, label):
    matrices = []
    labels = []

    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            df = pd.read_csv(file_path, skiprows=1, header=None)
            df = df.iloc[:, 1:]
            matrix = df.values.astype(np.float32)
            matrices.append(matrix)
            labels.append(label)

    return np.array(matrices), np.array(labels)

"""Load data => 1 for ADHD , 0 for control"""

X_adhd, y_adhd = load_data_from_folder(adhd_folder, 1)
X_control, y_control = load_data_from_folder(control_folder, 0)

# combining the data
X = np.concatenate((X_adhd, X_control), axis=0)
y = np.concatenate((y_adhd, y_control), axis=0)

"""1. Normalizing the data"""

scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X.reshape(-1, 19 * 19)).reshape(-1, 19, 19)

"""2. Adding a channel dimension for CNN input"""

X_reshaped = X_scaled.reshape(-1, 19, 19, 1)

"""3. Splitting the data"""

X_train, X_test, y_train, y_test = train_test_split(X_reshaped, y, test_size=0.2, random_state=42, stratify=y)
X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.1, random_state=42, stratify=y_train)

print(f"Training data shape: {X_train.shape}")
print(f"Validation data shape: {X_val.shape}")
print(f"Test data shape: {X_test.shape}")
print(f"Training labels shape: {y_train.shape}")
print(f"Validation labels shape: {y_val.shape}")
print(f"Test labels shape: {y_test.shape}")

"""Building the CNN Model"""

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

model = Sequential()

# Convolutional Layer 1
model.add(Conv2D(32, kernel_size=(3, 3), activation='relu', input_shape=(19, 19, 1)))
model.add(BatchNormalization())
model.add(MaxPooling2D(pool_size=(2, 2)))

# Convolutional Layer 2
model.add(Conv2D(64, kernel_size=(3, 3), activation='relu'))
model.add(BatchNormalization())
model.add(MaxPooling2D(pool_size=(2, 2)))

# Flatten the output
model.add(Flatten())

# Fully Connected Layer
model.add(Dense(128, activation='relu'))
model.add(Dropout(0.5))

# Output Layer
model.add(Dense(1, activation='sigmoid'))  # For binary classification

"""Compiling the model"""

model.compile(optimizer=Adam(learning_rate=0.001),loss='binary_crossentropy',metrics=['accuracy'])

"""Training the model"""

early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
model_checkpoint = ModelCheckpoint('best_cnn_model.keras', save_best_only=True)

history = model.fit(
    X_train, y_train,
    epochs=100,
    batch_size=16,
    validation_data=(X_val, y_val),
    callbacks=[early_stopping, model_checkpoint]
)

model.load_weights('best_cnn_model.keras')

"""Evaluating the model"""

test_loss, test_accuracy = model.evaluate(X_test, y_test)
print(f'Test Accuracy: {test_accuracy:.2f}')

from sklearn.metrics import classification_report

y_pred = (model.predict(X_test) > 0.5).astype("int32")
y_pred = y_pred.reshape(-1) # Reshape y_pred to be a 1D array
print(np.concatenate((y_test.reshape(-1, 1), y_pred.reshape(-1,1)), axis=1))
print(classification_report(y_test, y_pred))

import matplotlib.pyplot as plt

"""Plot accuracy"""

plt.plot(history.history['accuracy'], label='Train Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.legend()
plt.show()

"""Plot Loss"""

plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.legend()
plt.show()

"""Function to create pairs for the Siamese network"""

def create_pairs(X, y):
    pairs = []
    labels = []
    n = min([len(X[y == 0]), len(X[y == 1])])
    for i in range(n):
        pairs += [[X[y == 0][i], X[y == 1][i]]]
        labels += [1]
        neg_index = np.random.choice(np.where(y == 1)[0])
        pairs += [[X[y == 0][i], X[neg_index]]]
        labels += [0]
    return np.array(pairs), np.array(labels)

train_pairs, train_labels = create_pairs(X_train, y_train)
val_pairs, val_labels = create_pairs(X_val, y_val)

"""Base network"""

from tensorflow.keras.layers import RandomFlip, RandomRotation, RandomZoom

def create_base_network(input_shape):
    model = Sequential()
    model.add(RandomFlip("horizontal"))
    model.add(RandomRotation(0.1))
    model.add(RandomZoom(0.1))
    model.add(Conv2D(32, (5, 5), activation='relu', input_shape=input_shape))
    model.add(BatchNormalization())
    model.add(MaxPooling2D((2, 2)))
    model.add(Flatten())
    model.add(Dense(128, activation='relu'))
    model.add(Dropout(0.5))
    return model

#network using contrastive loss
# input_shape = (19, 19, 1)
# base_network = create_base_network(input_shape)

# input_a = Input(shape=input_shape)
# input_b = Input(shape=input_shape)

# feat_vecs_a = base_network(input_a)
# feat_vecs_b = base_network(input_b)

distance = Lambda(lambda tensors: tf.abs(tensors[0] - tensors[1]), output_shape=(128,))([feat_vecs_a, feat_vecs_b])
output = Dense(1, activation='sigmoid')(distance)
import tensorflow as tf

def contrastive_loss(margin=0.5):
    def loss(y_true, y_pred):
        return tf.reduce_mean((1 - y_true) * tf.square(y_pred) + y_true * tf.square(tf.maximum(margin - y_pred, 0)))
    return loss

def triplet_loss(margin):
    def loss(y_true, y_pred):
        anchor, positive, negative = y_pred[:, :128], y_pred[:, 128:256], y_pred[:, 256:]
        pos_dist = tf.reduce_sum(tf.square(anchor - positive), axis=1)
        neg_dist = tf.reduce_sum(tf.square(anchor - negative), axis=1)
        loss = tf.maximum(pos_dist - neg_dist + margin, 0.0)
        return tf.reduce_mean(loss)
    return loss


def create_triplets(X, y):
    triplets = []
    labels = []

    n = min(len(X[y == 0]), len(X[y == 1]))
    for i in range(n):
        anchor = X[y == 0][i]
        positive = X[y == 0][(i + 1) % n]

        neg_index = np.random.choice(np.where(y == 1)[0])
        negative = X[neg_index]

        triplets.append([anchor, positive, negative])
        labels.append(0)

    return np.array(triplets), np.array(labels)


train_triplets, train_labels = create_triplets(X_train, y_train)
val_triplets, val_labels = create_triplets(X_val, y_val)

input_shape = (19, 19, 1)
base_network = create_base_network(input_shape)

input_anchor = Input(shape=input_shape)
input_positive = Input(shape=input_shape)
input_negative = Input(shape=input_shape)

feat_vecs_anchor = base_network(input_anchor)
feat_vecs_positive = base_network(input_positive)
feat_vecs_negative = base_network(input_negative)

merged_output = tf.keras.layers.concatenate([feat_vecs_anchor, feat_vecs_positive, feat_vecs_negative], axis=1)

#model using contrastive loss
# siamese_model = Model(inputs=[input_a, input_b], outputs=output)
# siamese_model.compile(loss=contrastive_loss(margin=1), optimizer='adam', metrics=['accuracy'])

siamese_model = Model(inputs=[input_anchor, input_positive, input_negative], outputs=merged_output)
siamese_model.compile(loss=triplet_loss(margin=1.2), optimizer='adam', metrics=['accuracy'])


early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
model_checkpoint = ModelCheckpoint('siamese_model.keras', save_best_only=True, monitor='val_loss')

# Train the model for contrastive loss
# history = siamese_model.fit(
#     [train_pairs[:, 0], train_pairs[:, 1]], train_labels,
#     epochs=100,
#     batch_size=16,
#     validation_data=([val_pairs[:, 0], val_pairs[:, 1]], val_labels),
#     callbacks=[early_stopping, model_checkpoint]
# )
history = siamese_model.fit(
    [train_triplets[:, 0], train_triplets[:, 1], train_triplets[:, 2]], train_labels,
    epochs=100,
    batch_size=10,
    validation_data=([val_triplets[:, 0], val_triplets[:, 1], val_triplets[:, 2]], val_labels),
    callbacks=[early_stopping, model_checkpoint]
)

from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

def compute_distances(anchor, positive, negative):
    pos_dist = np.sum(np.square(anchor - positive), axis=1)
    neg_dist = np.sum(np.square(anchor - negative), axis=1)
    return pos_dist, neg_dist

test_triplets, test_labels = create_triplets(X_test, y_test)

embeddings = siamese_model.predict([test_triplets[:, 0], test_triplets[:, 1], test_triplets[:, 2]])

anchor_embeddings = embeddings[:, :128]
positive_embeddings = embeddings[:, 128:256]
negative_embeddings = embeddings[:, 256:]

pos_dist, neg_dist = compute_distances(anchor_embeddings, positive_embeddings, negative_embeddings)

y_pred = (pos_dist < neg_dist).astype(int)

print("Accuracy:", accuracy_score(test_labels, y_pred))
print(np.concatenate((test_labels.reshape(-1, 1), y_pred.reshape(-1,1)), axis=1))
print(confusion_matrix(test_labels, y_pred))
print(classification_report(test_labels, y_pred))