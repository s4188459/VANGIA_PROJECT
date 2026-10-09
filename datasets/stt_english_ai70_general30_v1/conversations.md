# English recording scripts — 70 AI/ML + 30 general

Version: ai70-general30-v1 · 2026-10-08

These are authored scripts, not verified reference transcripts. Read only the dialogue, not the title or speaker labels. Record one WAV per ID. After recording, listen and correct the corresponding reference draft to match what was actually spoken.

EN001–EN060 adapt topics from the user's AI_ML_Pipeline_Knowledge_Vault_v2.zip. EN061–EN070 add AI/ML topics. EN071–EN100 cover six other academic subjects. Topic order is for navigation, not a requirement for recording order.

Pilot: EN001, EN027, EN053, EN070, EN074. Read acronyms consistently; use the recording as the final authority for the transcript. For WER, document a consistent spelling policy for acronyms and numbers before comparing models.

## EN001 — Task definition [PILOT]

Subject: AI/ML · 56 words

**Student:** I want to build an AI model for our course project. Should I start by choosing an algorithm?

**Teacher:** Start with the problem. Describe the input, the output you need, and how you will judge whether the result is useful.

**Student:** So predicting a score is different from assigning a category?

**Teacher:** Exactly. Define the target before comparing models.

## EN002 — Supervised learning

Subject: AI/ML · 51 words

**Teacher:** What makes this learning task supervised?

**Student:** Each training example contains an input and a target that tells us the expected answer.

**Teacher:** Right. The model uses those pairs to learn a mapping that we hope will work on new examples.

**Student:** Then a label can be a number, not just a category name.

## EN003 — Unsupervised learning

Subject: AI/ML · 53 words

**Student:** Our dataset has measurements but no target labels. Can we still explore it with machine learning?

**Teacher:** Yes. Unsupervised methods can find structure, such as groups of similar observations.

**Student:** Would those groups automatically match the categories a teacher would choose?

**Teacher:** No. You still need to interpret the groups and decide whether they are useful.

## EN004 — Regression or classification

Subject: AI/ML · 51 words

**Teacher:** Suppose we predict how many minutes a journey will take. What kind of output do we need?

**Student:** A numerical estimate, so I would treat it as a regression task.

**Teacher:** And if we predict whether the journey will be short, medium, or long?

**Student:** Then we are predicting categories, so it becomes classification.

## EN005 — Binary classification

Subject: AI/ML · 54 words

**Student:** Our email dataset uses spam and not spam as labels. Does that count as binary classification?

**Teacher:** Yes. Each example belongs to one of two classes in this task.

**Student:** Does the model have to return the final label directly?

**Teacher:** It may first produce a score or probability, which a decision rule turns into a label.

## EN006 — Multiclass classification

Subject: AI/ML · 54 words

**Teacher:** We want to recognize one handwritten digit in each image. How many possible classes are there?

**Student:** Ten, from zero to nine, and each image has one correct digit label.

**Teacher:** Good. That is a multiclass problem with mutually exclusive labels.

**Student:** So we choose one class, even though the model may assign scores to all ten.

## EN007 — Multilabel classification

Subject: AI/ML · 53 words

**Student:** An image can show a dog outdoors at night. Should I force it into just one category?

**Teacher:** Not if all those labels matter. A multilabel model can predict several labels for the same image.

**Student:** Then outdoor and dog are separate decisions rather than competing alternatives?

**Teacher:** Exactly. Several labels can be true at once.

## EN008 — Features and targets

Subject: AI/ML · 60 words

**Student:** In our house dataset, are the floor area and the selling price both input features?

**Teacher:** That depends on your task. If you predict the selling price, it is the target, while floor area can be an input.

**Student:** So I should not accidentally include the answer among the features.

**Teacher:** Correct. Check what information would actually be available when making a prediction.

## EN009 — Training and validation

Subject: AI/ML · 51 words

**Teacher:** Why did you divide the data into training and validation sets?

**Student:** I fit the model on training examples and use validation examples to compare my choices.

**Teacher:** Does the validation set directly supply the usual training updates?

**Student:** No. It guides decisions such as model selection and settings, rather than ordinary parameter fitting.

## EN010 — Keeping a final test set

Subject: AI/ML · 56 words

**Student:** I keep checking the test score after every change. Is that still a fair final test?

**Teacher:** Those results are influencing your decisions, so the set is effectively becoming part of model selection.

**Student:** I should use validation data for those choices and reserve another set for the final evaluation.

**Teacher:** Yes. Clearly document which data influenced your decisions.

## EN011 — Principal components

Subject: AI/ML · 51 words

**Student:** Does principal component analysis predict the target for us?

**Teacher:** No. PCA transforms the input into new directions that capture variation in the data.

**Student:** Then I can keep fewer components and give that representation to another model?

**Teacher:** Yes, but retaining high variance does not guarantee that you retain everything useful for prediction.

## EN012 — Fitting preprocessing

Subject: AI/ML · 53 words

**Teacher:** When did you fit the PCA transformation in your experiment?

**Student:** I fitted it on the whole dataset before creating the training and test sets.

**Teacher:** That lets information from the test data influence preprocessing. Split first and fit the transformation on training data.

**Student:** Then I apply that same learned transformation to the other sets.

## EN013 — Embeddings

Subject: AI/ML · 50 words

**Student:** Is an embedding just a category number assigned to a word?

**Teacher:** An embedding is a vector representation. Its several numerical values can express relationships learned for a particular task.

**Student:** Does every dimension have an obvious meaning, like animal or location?

**Teacher:** Usually not. Useful relationships can be distributed across many dimensions.

## EN014 — Tokenization

Subject: AI/ML · 50 words

**Teacher:** Does a tokenizer always turn each word into exactly one token?

**Student:** I assumed it did, but a word might be split into smaller pieces.

**Teacher:** Correct. The tokenization depends on the tokenizer and the text, including language and punctuation.

**Student:** So counting words does not tell me the exact number of tokens.

## EN015 — Linear regression

Subject: AI/ML · 51 words

**Student:** How does linear regression combine several input features into a prediction?

**Teacher:** It multiplies each feature by a weight, adds those contributions, and includes an intercept.

**Student:** Training changes the weights to reduce the error on the training data?

**Teacher:** Yes. Remember that the result is a numerical prediction, rather than a class label.

## EN016 — Logistic regression

Subject: AI/ML · 54 words

**Student:** Why is logistic regression used for classification even though regression is in its name?

**Teacher:** In binary classification, it converts a linear score through a sigmoid function to estimate a class probability.

**Student:** Then a threshold turns that probability into a decision.

**Teacher:** Exactly. The probability estimate and the final decision are different parts of the process.

## EN017 — Nearest neighbours

Subject: AI/ML · 48 words

**Teacher:** How would k-nearest neighbours classify a new point?

**Student:** It finds nearby training examples and combines their labels, often by voting.

**Teacher:** What does that mean for the work needed at prediction time?

**Student:** It still needs to search stored examples, so prediction cost can become important as the dataset grows.

## EN018 — Decision trees

Subject: AI/ML · 55 words

**Student:** A decision tree seems like a sequence of questions. Is that a useful way to understand it?

**Teacher:** Yes. Each split uses a feature condition to send an example down a branch.

**Student:** Could a very deep tree memorize unusual details in the training set?

**Teacher:** It can, which is why controlling complexity and checking validation performance matter.

## EN019 — Random forests

Subject: AI/ML · 52 words

**Teacher:** What changes when we move from one decision tree to a random forest?

**Student:** We train multiple trees with randomness and combine their predictions.

**Teacher:** Why might that help compared with relying on one tree?

**Student:** Combining different trees can reduce sensitivity to the particular training sample, although we still need to evaluate the result.

## EN020 — Support vector machines

Subject: AI/ML · 55 words

**Student:** What does the margin mean in a support vector machine?

**Teacher:** It describes separation around the decision boundary. The method seeks a boundary with a large margin under its constraints.

**Student:** Are support vectors the examples that help determine that boundary?

**Teacher:** Yes. They are influential points associated with the margin, not a separate collection of output labels.

## EN021 — Naive Bayes assumptions

Subject: AI/ML · 53 words

**Student:** Why is the classifier called naive Bayes?

**Teacher:** It uses Bayes' rule with a simplifying assumption that features are conditionally independent given the class.

**Student:** Does that mean every word in a sentence is truly independent of the others?

**Teacher:** No. It is a modeling assumption that can be useful even when reality is more complicated.

## EN022 — Weights and bias

Subject: AI/ML · 51 words

**Teacher:** What is the difference between a weight and a bias in a neuron?

**Student:** A weight controls an input's contribution, while the bias shifts the value before activation.

**Teacher:** Good. Does the bias have to depend on the current input value?

**Student:** No. It is a learned parameter added separately from the weighted inputs.

## EN023 — Breaking symmetry

Subject: AI/ML · 51 words

**Student:** Why not initialize every hidden neuron with exactly the same weights?

**Teacher:** Symmetric neurons can produce the same output and receive the same updates, leaving them learning the same function.

**Student:** Different initial weights help them learn different transformations?

**Teacher:** Yes. Initialization should break that symmetry while keeping the scale of the values appropriate.

## EN024 — Hidden representations

Subject: AI/ML · 57 words

**Student:** Our input has three features, but the first hidden layer has four neurons. What goes into the next layer?

**Teacher:** The four activations produced by that hidden layer become its input vector.

**Student:** So the next layer does not simply receive the original three features again?

**Teacher:** In this sequential example, it receives the representation created by the preceding layer.

## EN025 — Nonlinear activation

Subject: AI/ML · 50 words

**Teacher:** What happens if we stack linear layers without nonlinear activations between them?

**Student:** I thought additional layers would automatically make the network more expressive.

**Teacher:** Their composition is still an affine transformation in this setting. Nonlinear activations allow more complex functions.

**Student:** So depth alone is not enough if every transformation stays linear.

## EN026 — ReLU activation

Subject: AI/ML · 47 words

**Student:** What does the ReLU activation do to a negative input?

**Teacher:** It outputs zero. For a positive input, it returns that input value.

**Student:** Then its output changes in a piecewise way, which introduces nonlinearity.

**Teacher:** Correct. It is an activation function, not the loss that compares predictions with targets.

## EN027 — Output activations [PILOT]

Subject: AI/ML · 48 words

**Student:** Should I use the same activation for every model output?

**Teacher:** Match the output to the task. A sigmoid is common for binary probabilities, while softmax is common for mutually exclusive classes.

**Student:** And ordinary numerical regression may use an unbounded output.

**Teacher:** Yes. The target's structure should guide that choice.

## EN028 — Forward pass

Subject: AI/ML · 43 words

**Teacher:** Does a forward pass update the network's weights?

**Student:** I used to think so, but it only computes predictions using the current parameters.

**Teacher:** What comes after that during a training step?

**Student:** We compute the loss, obtain gradients, and let the optimizer update the parameters.

## EN029 — Loss and metrics

Subject: AI/ML · 53 words

**Student:** Our model trains with one loss but the report lists several metrics. Is that inconsistent?

**Teacher:** No. The loss supplies a training signal, while evaluation metrics describe aspects of performance we care about.

**Student:** Then choosing a useful loss does not remove the need to choose appropriate metrics.

**Teacher:** Exactly. Explain both choices in your report.

## EN030 — Mean squared error

Subject: AI/ML · 48 words

**Teacher:** How does mean squared error treat a prediction that is far from the target?

**Student:** It squares the difference, so a large error contributes much more than a small one.

**Teacher:** Right. What else do we do after calculating those squared errors?

**Student:** We average them over the examples being evaluated.

## EN031 — Cross-entropy

Subject: AI/ML · 54 words

**Student:** What happens to cross-entropy when the model assigns a very low probability to the correct class?

**Teacher:** The loss becomes large. It penalizes being confidently wrong about that class.

**Student:** So a correct final label does not tell us the exact cross-entropy value.

**Teacher:** Correct. The loss also depends on the probability assigned to the correct answer.

## EN032 — Backpropagation

Subject: AI/ML · 44 words

**Teacher:** What does backpropagation calculate in a neural network?

**Student:** It calculates gradients of the loss with respect to parameters through the computational graph.

**Teacher:** Does it choose the learning rate for us?

**Student:** No. The optimizer uses the gradients, and the learning rate controls the update size.

## EN033 — Gradient descent

Subject: AI/ML · 50 words

**Student:** Why do we move opposite to the gradient during gradient descent?

**Teacher:** The gradient points toward local increase in the loss, so a suitable step in the opposite direction aims to reduce it.

**Student:** Does every possible step size guarantee improvement?

**Teacher:** No. An excessively large step can overshoot and increase the loss.

## EN034 — Learning rate

Subject: AI/ML · 52 words

**Teacher:** Your loss is jumping around after each update. What setting might you investigate?

**Student:** The learning rate might be too large, although I should check the data and implementation too.

**Teacher:** And what might happen if it is extremely small?

**Student:** Progress can be very slow, so I would compare reasonable values using validation results.

## EN035 — Training loop

Subject: AI/ML · 48 words

**Student:** Can I summarize training as forward, loss, backward, and update?

**Teacher:** Yes. The forward pass makes a prediction, the loss compares it with the target, and backward computes gradients.

**Student:** Then the optimizer changes the parameters before the next step.

**Teacher:** Exactly. Keep those stages separate when you explain the process.

## EN036 — Convolutional networks

Subject: AI/ML · 47 words

**Student:** Why are convolutional networks useful for image patterns?

**Teacher:** Convolutions apply shared filters across local regions, allowing a filter to detect a pattern at different positions.

**Student:** Does every position need its own completely separate filter weights?

**Teacher:** No. Sharing those weights is a key part of the convolution operation.

## EN037 — Recurrent networks

Subject: AI/ML · 45 words

**Teacher:** How does a recurrent neural network carry information through a sequence?

**Student:** It updates a hidden state as it processes successive inputs.

**Teacher:** What limitation can that introduce for computation?

**Student:** The dependence between steps limits parallel processing across time, and learning long-range relationships can also be difficult.

## EN038 — Confusion matrix

Subject: AI/ML · 49 words

**Student:** I understand correct predictions, but I keep mixing up false positives and false negatives.

**Teacher:** First define the positive class. A false positive predicts positive when the actual label is negative.

**Student:** Then a false negative misses an example that is actually positive.

**Teacher:** Correct. The confusion matrix separates those error types.

## EN039 — Precision

Subject: AI/ML · 45 words

**Teacher:** Our classifier flagged ten messages as spam, and eight really were spam. What is the precision?

**Student:** Eight out of ten, or eighty percent.

**Teacher:** Does that tell us how many of all the spam messages it found?

**Student:** No. We need recall to answer that different question.

## EN040 — Recall

Subject: AI/ML · 51 words

**Student:** There were twenty relevant documents, and the system retrieved fifteen of them. Is recall seventy-five percent?

**Teacher:** Yes, because recall compares the relevant items found with all the relevant items available.

**Student:** It does not use the total number of retrieved documents as its denominator.

**Teacher:** Correct. That denominator is used when calculating precision.

## EN041 — F1 score

Subject: AI/ML · 47 words

**Teacher:** Why might we report an F1 score alongside precision and recall?

**Student:** It combines them using their harmonic mean, so it reflects both kinds of performance.

**Teacher:** Does one F1 value tell us everything about the system's errors?

**Student:** No. I should still examine precision, recall, and the actual mistakes.

## EN042 — Decision threshold

Subject: AI/ML · 54 words

**Student:** If I lower the positive decision threshold, will the model flag more examples?

**Teacher:** For the same scores, yes. That can catch more actual positives, but it can also add false positives.

**Student:** So I need to choose a threshold according to the error trade-off.

**Teacher:** Exactly. A default cutoff is not automatically best for your task.

## EN043 — ROC area

Subject: AI/ML · 47 words

**Teacher:** Does ROC-AUC evaluate only the predictions made at a threshold of one half?

**Student:** No. It summarizes discrimination across thresholds using true-positive and false-positive rates.

**Teacher:** Does a high value automatically choose our operating threshold?

**Student:** No. We still need to decide which trade-off is appropriate when making actual decisions.

## EN044 — Precision-recall curves

Subject: AI/ML · 55 words

**Student:** Our positive class is rare. Why did you ask me to examine the precision-recall curve?

**Teacher:** It shows how well the model retrieves positives and how many predicted positives are correct across thresholds.

**Student:** So it can reveal behavior that a high overall accuracy might hide.

**Teacher:** Yes. Always connect the evaluation to the class you care about.

## EN045 — Regression metrics

Subject: AI/ML · 52 words

**Teacher:** How do mean absolute error and root mean squared error differ?

**Student:** Both can be expressed in the target's units, but squared errors make RMSE more sensitive to large misses.

**Teacher:** Should you choose whichever gives the smaller numerical score?

**Student:** No. I should choose based on which kinds of error matter for the task.

## EN046 — Percentage error

Subject: AI/ML · 51 words

**Student:** Can I use mean absolute percentage error if some target values are zero?

**Teacher:** Ordinary MAPE divides by the target magnitude, so zero targets cause a problem and near-zero targets can dominate.

**Student:** Then I should consider another metric and explain why.

**Teacher:** Yes. Check the target distribution before deciding how to measure error.

## EN047 — Statistical uncertainty

Subject: AI/ML · 50 words

**Student:** One model scored slightly better on our sample. Can I conclude it is definitely better in general?

**Teacher:** A small difference may reflect sampling variation. Consider uncertainty and whether the difference matters in practice.

**Student:** So I should avoid presenting a tiny improvement as conclusive.

**Teacher:** Correct. Describe the evidence and its limits.

## EN048 — Bootstrapping

Subject: AI/ML · 47 words

**Teacher:** How do you create a bootstrap sample from evaluation examples?

**Student:** I sample with replacement, so an example may appear several times while another may be absent.

**Teacher:** What can repeated bootstrap samples help us estimate?

**Student:** The variation of a statistic, which we can use in an uncertainty analysis.

## EN049 — Permutation testing

Subject: AI/ML · 55 words

**Student:** How is a permutation test different from simply reporting two scores?

**Teacher:** It compares the observed difference with a distribution generated under a specified null hypothesis.

**Student:** In a paired comparison, can we exchange the two systems' outcomes within examples when that assumption is appropriate?

**Teacher:** Yes. The shuffling scheme must match the hypothesis and the data structure.

## EN050 — K-fold validation

Subject: AI/ML · 45 words

**Teacher:** In five-fold cross-validation, how many folds train the model in each round?

**Student:** Four train it, and the remaining fold is used for evaluation. We rotate the held-out fold.

**Teacher:** Does getting five scores automatically constitute a significance test?

**Student:** No. Cross-validation and significance testing answer different questions.

## EN051 — Transformer blocks

Subject: AI/ML · 49 words

**Student:** Is a Transformer just one attention operation followed by a prediction?

**Teacher:** A Transformer typically stacks blocks that include attention and feed-forward processing, together with other components such as residual connections.

**Student:** So attention is important, but it is not the entire architecture.

**Teacher:** Exactly. Explain how representations move through the blocks.

## EN052 — Position information

Subject: AI/ML · 47 words

**Teacher:** Why does a text model need information about token order?

**Student:** The same words in a different order can express a different meaning.

**Teacher:** Can token embeddings alone always supply the intended positions?

**Student:** No. The architecture needs a mechanism to represent position, such as positional encodings or rotary embeddings.

## EN053 — Queries keys and values [PILOT]

Subject: AI/ML · 53 words

**Student:** Are queries, keys, and values three unrelated copies of the input?

**Teacher:** They are projections of representations, learned for different roles within attention.

**Student:** Queries and keys produce compatibility scores, while values provide the information being combined?

**Teacher:** That is a useful starting intuition. The resulting vector is still a representation, not a word by itself.

## EN054 — Scaling attention scores

Subject: AI/ML · 41 words

**Teacher:** What happens before softmax in scaled dot-product attention?

**Student:** We calculate query-key dot products and divide by the square root of the key dimension.

**Teacher:** Why include that scale factor?

**Student:** It helps control the magnitude of the scores as the key dimension grows.

## EN055 — Attention output

Subject: AI/ML · 47 words

**Student:** After softmax, do the attention weights directly tell us the next token?

**Teacher:** No. They weight the value vectors to create a contextual representation.

**Student:** That representation still passes through further model processing before vocabulary scores are produced.

**Teacher:** Correct. Do not confuse attention weights with the final token distribution.

## EN056 — Multiple attention heads

Subject: AI/ML · 46 words

**Teacher:** Why use more than one attention head?

**Student:** Different learned projections can capture different useful relationships between positions.

**Teacher:** Do we assign one fixed human meaning to every head before training?

**Student:** Usually not. Their behavior is learned, and a head does not necessarily correspond to one simple concept.

## EN057 — Causal masking

Subject: AI/ML · 51 words

**Student:** During causal language-model training, can a position attend to later answer tokens?

**Teacher:** The causal mask blocks future positions. It can attend to allowed earlier positions and itself.

**Student:** That prevents the prediction from using future context it would not have during generation.

**Teacher:** Exactly. The mask enforces the intended direction of information flow.

## EN058 — Autoregressive generation

Subject: AI/ML · 43 words

**Teacher:** How does an autoregressive language model extend a prompt?

**Student:** It predicts a distribution for the next token, selects a token, appends it, and repeats.

**Teacher:** Does it produce the entire answer in one classification decision?

**Student:** No. The answer is built through successive decoding steps.

## EN059 — Key-value caching

Subject: AI/ML · 54 words

**Student:** Why do we keep a key-value cache during autoregressive decoding?

**Teacher:** It lets a new position reuse previously computed keys and values instead of recomputing that history each step.

**Student:** We still calculate a new query, key, and value for the newly processed position?

**Teacher:** Yes, and the new key and value are added to the cache.

## EN060 — Rotary position embeddings

Subject: AI/ML · 45 words

**Teacher:** Where does rotary position information enter attention in the setup we studied?

**Student:** RoPE rotates pairs of dimensions in queries and keys according to their positions.

**Teacher:** Is RoPE an activation function like ReLU?

**Student:** No. It represents position inside attention, helping query-key interactions reflect relative positional relationships.

## EN061 — Overfitting

Subject: AI/ML · 53 words

**Student:** Training performance keeps improving, but validation performance is getting worse. What could explain that?

**Teacher:** The model may be fitting details that do not generalize beyond the training examples.

**Student:** So a lower training loss is not sufficient evidence that the model improved.

**Teacher:** Correct. Inspect the validation results and check for other causes as well.

## EN062 — Underfitting

Subject: AI/ML · 51 words

**Teacher:** Your model performs poorly on both training and validation examples. What possibility would you investigate?

**Student:** It may be underfitting, perhaps because the representation or model is too limited.

**Teacher:** Is a larger model always the first solution?

**Student:** No. I should also check data quality, useful features, and whether training is working correctly.

## EN063 — Regularization

Subject: AI/ML · 51 words

**Student:** How can regularization help when a model fits the training set too closely?

**Teacher:** Some forms add a penalty that discourages overly large parameter values and changes the objective being optimized.

**Student:** Can making the penalty very strong also hurt performance?

**Teacher:** Yes. Too much regularization can make the model fit useful patterns poorly.

## EN064 — Early stopping

Subject: AI/ML · 53 words

**Teacher:** Why did you save the checkpoint with the best validation result instead of the final training checkpoint?

**Student:** Later training did not improve validation performance, so I used early stopping to avoid continuing indefinitely.

**Teacher:** Did you use the final test set to choose that checkpoint?

**Student:** No. The checkpoint choice was based on validation data.

## EN065 — Mini-batches and epochs

Subject: AI/ML · 50 words

**Student:** Are a batch and an epoch the same thing?

**Teacher:** No. A mini-batch contains a subset processed in one step, while an epoch usually means one pass through the training set.

**Student:** Then one epoch can include many parameter updates.

**Teacher:** Exactly. State both batch size and training duration when describing your experiment.

## EN066 — Feature scaling

Subject: AI/ML · 44 words

**Teacher:** Why might feature scaling matter for a distance-based classifier?

**Student:** A feature measured on a much larger numerical scale can dominate the distance calculation.

**Teacher:** Where should you learn the scaling parameters?

**Student:** From the training data, then apply the same transformation to validation and test examples.

## EN067 — Missing values

Subject: AI/ML · 48 words

**Student:** Some measurements are missing. Should I replace every missing value with zero?

**Teacher:** Only if zero has an appropriate meaning. Otherwise, you could introduce a misleading pattern.

**Student:** I should examine why values are missing and choose a documented handling strategy.

**Teacher:** Yes. Fit any learned imputation rule using training data.

## EN068 — Duplicate data leakage

Subject: AI/ML · 50 words

**Teacher:** These training and test examples look almost identical. Why could that be a problem?

**Student:** The evaluation may reward remembering examples rather than handling genuinely new data.

**Teacher:** What would you check before trusting the score?

**Student:** I would look for duplicates and related groups that should stay together when splitting the dataset.

## EN069 — Distribution shift

Subject: AI/ML · 52 words

**Student:** Our model worked on quiet recordings, but it struggles with noisy classroom audio. Why?

**Teacher:** The conditions differ from the data used to develop and evaluate it. That is one form of distribution shift.

**Student:** Then our evaluation should include the conditions we expect in practice.

**Teacher:** Yes. Describe which environments your evidence actually covers.

## EN070 — Speech recognition evaluation [PILOT]

Subject: AI/ML · 43 words

**Teacher:** What does word error rate count in our speech-recognition benchmark?

**Student:** Substitutions, deletions, and insertions, divided by the number of reference words.

**Teacher:** What must we prepare before that score is meaningful?

**Student:** A checked reference transcript and consistent text-normalization rules for every model being compared.

## EN071 — Adding fractions

Subject: Mathematics · 53 words

**Student:** Why can I not add the denominators when adding one half and one quarter?

**Teacher:** They describe different sizes of parts. First express both fractions with the same denominator.

**Student:** One half becomes two quarters, so the sum is three quarters.

**Teacher:** Correct. Drawing one whole divided into four equal parts can make the reasoning clearer.

## EN072 — Area and perimeter

Subject: Mathematics · 46 words

**Teacher:** A rectangle is eight centimeters long and three centimeters wide. How do area and perimeter differ?

**Student:** Area measures the space inside, while perimeter measures the distance around the edge.

**Teacher:** What are their values here?

**Student:** The area is twenty-four square centimeters, and the perimeter is twenty-two centimeters.

## EN073 — Negative numbers

Subject: Mathematics · 50 words

**Student:** The temperature falls from two degrees to minus three degrees. Is the change one degree?

**Teacher:** Use a number line. You move two degrees to zero and another three below zero.

**Student:** Then the temperature decreases by five degrees.

**Teacher:** Exactly. Keep the direction of change separate from the size of the change.

## EN074 — Solving an equation [PILOT]

Subject: Mathematics · 45 words

**Teacher:** How would you solve three x plus five equals twenty?

**Student:** I subtract five from both sides, leaving three x equals fifteen.

**Teacher:** What is your next step?

**Student:** Divide both sides by three, so x equals five. I can substitute it into the original equation to check.

## EN075 — Probability of a coin toss

Subject: Mathematics · 51 words

**Student:** A fair coin landed on heads three times. Is tails more likely on the next toss?

**Teacher:** Not if the tosses are independent. Each new toss still has an equal chance of heads or tails.

**Student:** The next outcome does not have to balance the previous ones.

**Teacher:** Correct. Short sequences can look uneven.

## EN076 — Evaporation

Subject: Science · 51 words

**Student:** Water disappeared from our open dish even though it never boiled. What happened?

**Teacher:** Some liquid water became water vapor and entered the surrounding air through evaporation.

**Student:** So evaporation can occur below the boiling point?

**Teacher:** Yes. It happens at the surface, and its rate depends on conditions such as temperature and airflow.

## EN077 — Photosynthesis

Subject: Science · 47 words

**Teacher:** What role does light play in photosynthesis?

**Student:** It supplies energy for plants to produce sugars from carbon dioxide and water.

**Teacher:** Then is it accurate to say plants obtain all their food directly from soil?

**Student:** No. Taking up water and minerals through roots is different from producing sugars.

## EN078 — Electrical circuits

Subject: Science · 46 words

**Student:** Why does the bulb go out when I open this switch?

**Teacher:** Opening the switch breaks the conducting path in this simple circuit.

**Student:** So the current no longer flows through the bulb along that path.

**Teacher:** Correct. Draw the complete circuit and mark where the connection is interrupted.

## EN079 — Mass and weight

Subject: Science · 44 words

**Teacher:** Are mass and weight exactly the same physical quantity?

**Student:** No. Mass describes a property of matter, while weight is a gravitational force.

**Teacher:** What happens to an object's weight in a weaker gravitational field?

**Student:** It becomes smaller, even though the object's mass remains the same.

## EN080 — Experimental controls

Subject: Science · 51 words

**Student:** We want to compare plant growth under different amounts of light. Can we also change the soil type?

**Teacher:** Changing both makes it harder to identify which factor explains the difference.

**Student:** We should keep the other relevant conditions as similar as possible.

**Teacher:** Yes, and define how and when you will measure growth.

## EN081 — Past simple and present perfect

Subject: English · 50 words

**Student:** I wrote, I have visited the museum yesterday. What should I change?

**Teacher:** With the finished time yesterday, use the past simple: I visited the museum yesterday.

**Student:** Could I say, I have visited that museum before, without naming a finished time?

**Teacher:** Yes. That sentence describes experience without specifying when it happened.

## EN082 — Interested and interesting

Subject: English · 42 words

**Teacher:** How would you describe your feeling about this topic?

**Student:** I am interesting in astronomy. Is that correct?

**Teacher:** Say interested when describing your feeling. Interesting describes something that attracts your attention.

**Student:** Then I am interested in astronomy because I find the subject interesting.

## EN083 — Subject-verb agreement

Subject: English · 51 words

**Student:** My sentence says, The results of the experiment shows a pattern. Which part is wrong?

**Teacher:** The subject is results, so the verb should be show.

**Student:** I chose shows because experiment is singular and sits near the verb.

**Teacher:** Find the main noun in the subject before deciding which verb form to use.

## EN084 — Finding the main idea

Subject: English · 46 words

**Teacher:** What belongs in a short summary of this passage?

**Student:** The main message and the most important supporting points, rather than every small example.

**Teacher:** Should you copy whole paragraphs to make sure nothing is missing?

**Student:** No. I should explain the central ideas concisely in my own words.

## EN085 — Evidence in an essay

Subject: English · 48 words

**Student:** I added several quotations, but my paragraph still feels weak. What is missing?

**Teacher:** Explain how each quotation supports the point you are making.

**Student:** So evidence does not replace my own reasoning.

**Teacher:** Exactly. Your reader needs to understand why you selected it and how it connects to your claim.

## EN086 — Weather and climate

Subject: Geography · 53 words

**Student:** It was unusually cold today. Does one cold day tell us that the climate has changed?

**Teacher:** Weather describes short-term conditions, while climate concerns patterns over much longer periods.

**Student:** Then we need long-term evidence instead of drawing a conclusion from a single day.

**Teacher:** Correct. Match the time scale of the evidence to the question.

## EN087 — Map scale

Subject: Geography · 48 words

**Teacher:** On this map, one centimeter represents two kilometers. What does a three-centimeter straight line represent?

**Student:** Six kilometers in a straight line.

**Teacher:** Would the actual road journey necessarily be six kilometers?

**Student:** No. The road may curve or take a longer route than the direct distance shown by that line.

## EN088 — Latitude and longitude

Subject: Geography · 53 words

**Student:** I keep confusing latitude with longitude. Which one measures distance north or south of the equator in degrees?

**Teacher:** Latitude does. Longitude describes angular position east or west of the prime meridian.

**Student:** So both coordinates are needed to identify a location precisely on a map.

**Teacher:** Yes. Also keep their order and directional signs consistent.

## EN089 — The water cycle

Subject: Geography · 46 words

**Teacher:** What happens after water vapor cools and condenses into cloud droplets?

**Student:** Under suitable conditions, water can return to the surface as precipitation.

**Teacher:** Does all that water immediately flow into a river?

**Student:** No. Some infiltrates the ground, some is stored, and some eventually returns to the atmosphere.

## EN090 — River erosion

Subject: Geography · 51 words

**Student:** Why does a river carry sediment away from some places and deposit it in others?

**Teacher:** Its capacity to transport material depends on flow conditions and the properties of the sediment.

**Student:** When conditions no longer support carrying certain particles, they may settle.

**Teacher:** Correct. Erosion, transport, and deposition help shape the river landscape.

## EN091 — Primary sources

Subject: History · 49 words

**Teacher:** What makes a diary written during an event a primary source for studying that event?

**Student:** It provides evidence from someone recording experiences at the time.

**Teacher:** Does that automatically make every statement in the diary accurate?

**Student:** No. We should still consider the writer's perspective, knowledge, and possible reasons for writing.

## EN092 — Chronology and causation

Subject: History · 48 words

**Student:** These two events happened one after another. Does that prove the first caused the second?

**Teacher:** No. Chronological order alone is not enough to establish a causal connection.

**Student:** I need evidence explaining how one event contributed to the other.

**Teacher:** Yes, and consider alternative explanations and the broader historical context.

## EN093 — Comparing historical accounts

Subject: History · 48 words

**Teacher:** Two accounts describe the same event differently. What should you investigate?

**Student:** Who wrote them, when they were written, what the authors knew, and their intended audiences.

**Teacher:** Should you simply choose the account that agrees with your first impression?

**Student:** No. I should compare the claims with other available evidence.

## EN094 — Industrialization

Subject: History · 51 words

**Student:** Can I explain industrialization only as the invention of new machines?

**Teacher:** Machinery is important, but also consider changes in production, labor, energy use, and the organization of work.

**Student:** Then my answer should connect technological changes with social and economic changes.

**Teacher:** Exactly. Avoid reducing a broad historical process to a single invention.

## EN095 — Historical arguments

Subject: History · 46 words

**Teacher:** Your essay lists events clearly, but where is the argument?

**Student:** I need to state what I think explains the change and support that interpretation with evidence.

**Teacher:** Should you mention evidence that complicates your explanation?

**Student:** Yes. Addressing it helps show the limits and strength of my argument.

## EN096 — Variables in programming

Subject: Computing · 58 words

**Student:** If I assign a new value to a variable, does that always change every other variable with a similar name?

**Teacher:** No. Similar names do not establish a connection. Behavior depends on assignments, references, and the language's rules.

**Student:** So I should trace which value or object each variable actually refers to.

**Teacher:** Exactly. Names alone do not determine data flow.

## EN097 — Loops and stopping conditions

Subject: Computing · 48 words

**Teacher:** Why does your loop keep running after the expected number of steps?

**Student:** I forgot to update the counter used in the stopping condition.

**Teacher:** How can you check that without guessing?

**Student:** Trace the counter and condition after each iteration, then verify that the loop eventually reaches its stopping state.

## EN098 — Debugging an index error

Subject: Computing · 57 words

**Student:** My program reports an index error when it reads the last item in the list.

**Teacher:** Check the valid index range and the value your loop produces at its final iteration.

**Student:** I used the length of the list as an index, but indexing starts at zero here.

**Teacher:** Right. The last valid index is one less than the length.

## EN099 — Database keys

Subject: Computing · 43 words

**Teacher:** Why does this student table need a primary key?

**Student:** It provides a way to identify each row uniquely.

**Teacher:** Would a student's first name be a reliable choice?

**Student:** Usually not, because different students can share a name. A suitable unique identifier avoids that ambiguity.

## EN100 — Testing software

Subject: Computing · 55 words

**Student:** My program works for the example in the assignment. Can I assume it handles every input?

**Teacher:** No. Try different valid cases and the boundary conditions specified by the task.

**Student:** I should also check how it handles invalid input when the requirements include that behavior.

**Teacher:** Yes. Record what you expected and what the program actually did.

