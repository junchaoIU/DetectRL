"""
Augmenter Recipes:
===================

Transformations and constraints can be used for simple NLP data augmentations. Here is a list of recipes for NLP data augmentations

"""
import random

from textattack.constraints.pre_transformation import (
    RepeatModification,
    StopwordModification,
)
from textattack.constraints.semantics.sentence_encoders import UniversalSentenceEncoder

from . import Augmenter

DEFAULT_CONSTRAINTS = [RepeatModification(), StopwordModification()]


class EasyDataAugmenter(Augmenter):
    """An implementation of Easy Data Augmentation, which combines:

    - WordNet synonym replacement
        - Randomly replace words with their synonyms.
    - Word deletion
        - Randomly remove words from the sentence.
    - Word order swaps
        - Randomly swap the position of words in the sentence.
    - Random synonym insertion
        - Insert a random synonym of a random word at a random location.

    in one augmentation method.

    "EDA: Easy Data Augmentation Techniques for Boosting Performance on Text Classification Tasks" (Wei and Zou, 2019)
    https://arxiv.org/abs/1901.11196
    """

    def __init__(self, pct_words_to_swap=0.1, transformations_per_example=4):
        assert 0.0 <= pct_words_to_swap <= 1.0, "pct_words_to_swap must be in [0., 1.]"
        assert (
                transformations_per_example > 0
        ), "transformations_per_example must be a positive integer"
        self.pct_words_to_swap = pct_words_to_swap
        self.transformations_per_example = transformations_per_example
        n_aug_each = max(transformations_per_example // 4, 1)

        self.synonym_replacement = WordNetAugmenter(
            pct_words_to_swap=pct_words_to_swap,
            transformations_per_example=n_aug_each,
        )
        self.random_deletion = DeletionAugmenter(
            pct_words_to_swap=pct_words_to_swap,
            transformations_per_example=n_aug_each,
        )
        self.random_swap = SwapAugmenter(
            pct_words_to_swap=pct_words_to_swap,
            transformations_per_example=n_aug_each,
        )
        self.random_insertion = SynonymInsertionAugmenter(
            pct_words_to_swap=pct_words_to_swap, transformations_per_example=n_aug_each
        )

    def augment(self, text):
        augmented_text = []
        augmented_text += self.synonym_replacement.augment(text)
        augmented_text += self.random_deletion.augment(text)
        augmented_text += self.random_swap.augment(text)
        augmented_text += self.random_insertion.augment(text)
        augmented_text = list(set(augmented_text))
        random.shuffle(augmented_text)
        return augmented_text[: self.transformations_per_example]

    def __repr__(self):
        return "EasyDataAugmenter"


class SwapAugmenter(Augmenter):
    def __init__(self, **kwargs):
        from textattack.transformations import WordInnerSwapRandom

        transformation = WordInnerSwapRandom()
        super().__init__(transformation, constraints=DEFAULT_CONSTRAINTS, **kwargs)


class SynonymInsertionAugmenter(Augmenter):
    def __init__(self, **kwargs):
        from textattack.transformations import WordInsertionRandomSynonym

        transformation = WordInsertionRandomSynonym()
        super().__init__(transformation, constraints=DEFAULT_CONSTRAINTS, **kwargs)


class WordNetAugmenter(Augmenter):
    """Augments text by replacing with synonyms from the WordNet thesaurus."""

    def __init__(self, **kwargs):
        from textattack.transformations import WordSwapWordNet

        transformation = WordSwapWordNet()
        super().__init__(transformation, constraints=DEFAULT_CONSTRAINTS, **kwargs)


class DeletionAugmenter(Augmenter):
    def __init__(self, **kwargs):
        from textattack.transformations import WordDeletion

        transformation = WordDeletion()
        super().__init__(transformation, constraints=DEFAULT_CONSTRAINTS, **kwargs)


class EmbeddingAugmenter(Augmenter):
    """Augments text by transforming words with their embeddings."""

    def __init__(self, **kwargs):
        from textattack.transformations import WordSwapEmbedding

        transformation = WordSwapEmbedding(max_candidates=50)
        from textattack.constraints.semantics import WordEmbeddingDistance

        constraints = DEFAULT_CONSTRAINTS + [WordEmbeddingDistance(min_cos_sim=0.8)]
        super().__init__(transformation, constraints=constraints, **kwargs)


class CharSwapAugmenter(Augmenter):
    """Augments words by swapping characters out for other characters."""

    def __init__(self, **kwargs):
        from textattack.transformations import (
            CompositeTransformation,
            WordSwapNeighboringCharacterSwap,
            WordSwapRandomCharacterDeletion,
            WordSwapRandomCharacterInsertion,
            WordSwapRandomCharacterSubstitution,
        )

        transformation = CompositeTransformation(
            [
                # (1) Swap: Swap two adjacent letters in the word.
                WordSwapNeighboringCharacterSwap(),
                # (2) Substitution: Substitute a letter in the word with a random letter.
                WordSwapRandomCharacterSubstitution(),
                # (3) Deletion: Delete a random letter from the word.
                WordSwapRandomCharacterDeletion(),
                # (4) Insertion: Insert a random letter in the word.
                WordSwapRandomCharacterInsertion(),
            ]
        )
        super().__init__(transformation, constraints=DEFAULT_CONSTRAINTS, **kwargs)


class CheckListAugmenter(Augmenter):
    """Augments words by using the transformation methods provided by CheckList
    INV testing, which combines:

    - Name Replacement
    - Location Replacement
    - Number Alteration
    - Contraction/Extension

    "Beyond Accuracy: Behavioral Testing of NLP models with CheckList" (Ribeiro et al., 2020)
    https://arxiv.org/abs/2005.04118
    """

    def __init__(self, **kwargs):
        from textattack.transformations import (
            CompositeTransformation,
            WordSwapChangeLocation,
            WordSwapChangeName,
            WordSwapChangeNumber,
            WordSwapContract,
            WordSwapExtend,
        )

        transformation = CompositeTransformation(
            [
                WordSwapChangeNumber(),
                WordSwapChangeLocation(),
                WordSwapChangeName(),
                WordSwapExtend(),
                WordSwapContract(),
            ]
        )

        constraints = [DEFAULT_CONSTRAINTS[0]]

        super().__init__(transformation, constraints=constraints, **kwargs)


class CLAREAugmenter(Augmenter):
    """Li, Zhang, Peng, Chen, Brockett, Sun, Dolan.

    "Contextualized Perturbation for Textual Adversarial Attack" (Li et
    al., 2020)

    https://arxiv.org/abs/2009.07502

    CLARE builds on a pre-trained masked language model and modifies the inputs in a contextaware manner.
    We propose three contextualized perturbations, Replace, Insert and Merge, allowing for generating outputs
    of varied lengths.
    """

    def __init__(
            self, model="distilroberta-base", tokenizer="distilroberta-base", **kwargs
    ):
        import transformers

        from textattack.transformations import (
            CompositeTransformation,
            WordInsertionMaskedLM,
            WordMergeMaskedLM,
            WordSwapMaskedLM,
        )

        shared_masked_lm = transformers.AutoModelForCausalLM.from_pretrained(model)
        shared_tokenizer = transformers.AutoTokenizer.from_pretrained(tokenizer)

        transformation = CompositeTransformation(
            [
                WordSwapMaskedLM(
                    method="bae",
                    masked_language_model=shared_masked_lm,
                    tokenizer=shared_tokenizer,
                    max_candidates=50,
                    min_confidence=5e-4,
                ),
                WordInsertionMaskedLM(
                    masked_language_model=shared_masked_lm,
                    tokenizer=shared_tokenizer,
                    max_candidates=50,
                    min_confidence=0.0,
                ),
                WordMergeMaskedLM(
                    masked_language_model=shared_masked_lm,
                    tokenizer=shared_tokenizer,
                    max_candidates=50,
                    min_confidence=5e-3,
                ),
            ]
        )

        use_constraint = UniversalSentenceEncoder(
            threshold=0.7,
            metric="cosine",
            compare_against_original=True,
            window_size=15,
            skip_text_shorter_than_window=True,
        )

        constraints = DEFAULT_CONSTRAINTS + [use_constraint]

        super().__init__(transformation, constraints=constraints, **kwargs)


class PruthiAugmenter(Augmenter):
    """An implementation of the attack used in "Combating Adversarial
    Misspellings with Robust Word Recognition", Pruthi et al., 2019.

    This attack focuses on a small number of character-level changes that simulate common typos. It combines:
        - Swapping neighboring characters
        - Deleting characters
        - Inserting characters
        - Swapping characters for adjacent keys on a QWERTY keyboard.

    https://arxiv.org/abs/1905.11268
    """

    def __init__(
            self, max_num_word_swaps=1, **kwargs
    ):
        import transformers

        from textattack.transformations import (
            CompositeTransformation,
            WordSwapNeighboringCharacterSwap,
            WordSwapRandomCharacterDeletion,
            WordSwapRandomCharacterInsertion,
            WordSwapQWERTY,
        )

        from textattack.constraints.pre_transformation import (
            MinWordLength,
            RepeatModification,
            StopwordModification,
        )

        from textattack.constraints.overlap import MaxWordsPerturbed

        transformation = CompositeTransformation(
            [
                WordSwapNeighboringCharacterSwap(
                    random_one=False, skip_first_char=True, skip_last_char=True
                ),
                WordSwapRandomCharacterDeletion(
                    random_one=False, skip_first_char=True, skip_last_char=True
                ),
                WordSwapRandomCharacterInsertion(
                    random_one=False, skip_first_char=True, skip_last_char=True
                ),
                WordSwapQWERTY(
                    random_one=False, skip_first_char=True, skip_last_char=True
                ),
            ]
        )

        constraints = [
            MinWordLength(min_length=4),
            StopwordModification(),
            MaxWordsPerturbed(max_num_words=max_num_word_swaps),
            RepeatModification(),
        ]

        super().__init__(transformation, constraints=constraints, **kwargs)


class TextBuggerAugmenter(Augmenter):
    """Li, J., Ji, S., Du, T., Li, B., and Wang, T. (2018).
    TextBugger: Generating Adversarial Text Against Real-world Applications.

    https://arxiv.org/abs/1812.05271
    """

    def __init__(
            self, **kwargs
    ):
        from textattack.transformations import (
            CompositeTransformation,
            WordSwapEmbedding,
            WordSwapHomoglyphSwap,
            WordSwapNeighboringCharacterSwap,
            WordSwapRandomCharacterDeletion,
            WordSwapRandomCharacterInsertion,
        )

        transformation = CompositeTransformation(
            [
                # (1) Insert: Insert a space into the word.
                # Generally, words are segmented by spaces in English. Therefore,
                # we can deceive classifiers by inserting spaces into words.
                WordSwapRandomCharacterInsertion(
                    random_one=True,
                    letters_to_insert=" ",
                    skip_first_char=True,
                    skip_last_char=True,
                ),
                # (2) Delete: Delete a random character of the word except for the first
                # and the last character.
                WordSwapRandomCharacterDeletion(
                    random_one=True, skip_first_char=True, skip_last_char=True
                ),
                # (3) Swap: Swap random two adjacent letters in the word but do not
                # alter the first or last letter. This is a common occurrence when
                # typing quickly and is easy to implement.
                WordSwapNeighboringCharacterSwap(
                    random_one=True, skip_first_char=True, skip_last_char=True
                ),
                # (4) Substitute-C (Sub-C): Replace characters with visually similar
                # characters (e.g., replacing “o” with “0”, “l” with “1”, “a” with “@”)
                # or adjacent characters in the keyboard (e.g., replacing “m” with “n”).
                WordSwapHomoglyphSwap(),
                # (5) Substitute-W
                # (Sub-W): Replace a word with its topk nearest neighbors in a
                # context-aware word vector space. Specifically, we use the pre-trained
                # GloVe model [30] provided by Stanford for word embedding and set
                # topk = 5 in the experiment.
                WordSwapEmbedding(max_candidates=5),
            ]
        )

        use_constraint = UniversalSentenceEncoder(threshold=0.8)

        constraints = DEFAULT_CONSTRAINTS + [use_constraint]

        super().__init__(transformation, constraints=constraints, **kwargs)


class TextFoolerAugmenter(Augmenter):
    """Jin, D., Jin, Z., Zhou, J.T., & Szolovits, P. (2019).

    Is BERT Really Robust? Natural Language Attack on Text
    Classification and Entailment.

    https://arxiv.org/abs/1907.11932
    """

    def __init__(
            self, **kwargs
    ):
        from textattack.transformations import (
            WordSwapEmbedding,
        )

        from textattack.constraints.pre_transformation import (
            InputColumnModification,
            RepeatModification,
            StopwordModification,
        )
        from textattack.constraints.grammaticality import PartOfSpeech
        from textattack.constraints.semantics import WordEmbeddingDistance

        transformation = WordSwapEmbedding(max_candidates=50)

        # Don't modify the same word twice or the stopwords defined
        # in the TextFooler public implementation.
        #
        # fmt: off
        stopwords = set(
            ["a", "about", "above", "across", "after", "afterwards", "again", "against", "ain", "all", "almost",
             "alone", "along", "already", "also", "although", "am", "among", "amongst", "an", "and", "another", "any",
             "anyhow", "anyone", "anything", "anyway", "anywhere", "are", "aren", "aren't", "around", "as", "at",
             "back", "been", "before", "beforehand", "behind", "being", "below", "beside", "besides", "between",
             "beyond", "both", "but", "by", "can", "cannot", "could", "couldn", "couldn't", "d", "didn", "didn't",
             "doesn", "doesn't", "don", "don't", "down", "due", "during", "either", "else", "elsewhere", "empty",
             "enough", "even", "ever", "everyone", "everything", "everywhere", "except", "first", "for", "former",
             "formerly", "from", "hadn", "hadn't", "hasn", "hasn't", "haven", "haven't", "he", "hence", "her", "here",
             "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his", "how", "however",
             "hundred", "i", "if", "in", "indeed", "into", "is", "isn", "isn't", "it", "it's", "its", "itself", "just",
             "latter", "latterly", "least", "ll", "may", "me", "meanwhile", "mightn", "mightn't", "mine", "more",
             "moreover", "most", "mostly", "must", "mustn", "mustn't", "my", "myself", "namely", "needn", "needn't",
             "neither", "never", "nevertheless", "next", "no", "nobody", "none", "noone", "nor", "not", "nothing",
             "now", "nowhere", "o", "of", "off", "on", "once", "one", "only", "onto", "or", "other", "others",
             "otherwise", "our", "ours", "ourselves", "out", "over", "per", "please", "s", "same", "shan", "shan't",
             "she", "she's", "should've", "shouldn", "shouldn't", "somehow", "something", "sometime", "somewhere",
             "such", "t", "than", "that", "that'll", "the", "their", "theirs", "them", "themselves", "then", "thence",
             "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they", "this", "those",
             "through", "throughout", "thru", "thus", "to", "too", "toward", "towards", "under", "unless", "until",
             "up", "upon", "used", "ve", "was", "wasn", "wasn't", "we", "were", "weren", "weren't", "what", "whatever",
             "when", "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon",
             "wherever", "whether", "which", "while", "whither", "who", "whoever", "whole", "whom", "whose", "why",
             "with", "within", "without", "won", "won't", "would", "wouldn", "wouldn't", "y", "yet", "you", "you'd",
             "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"]
        )

        #
        # During entailment, we should only edit the hypothesis - keep the premise
        # the same.
        #
        input_column_modification = InputColumnModification(
            ["premise", "hypothesis"], {"premise"}
        )

        use_constraint = UniversalSentenceEncoder(
            threshold=0.840845057,
            metric="angular",
            compare_against_original=False,
            window_size=15,
            skip_text_shorter_than_window=True,
        )
        constraints = [RepeatModification(), StopwordModification(stopwords=stopwords), input_column_modification, WordEmbeddingDistance(min_cos_sim=0.5), PartOfSpeech(allow_verb_noun_swap=True)] + [use_constraint]

        super().__init__(transformation, constraints=constraints, **kwargs)


class DeepWordBugAugmenter(Augmenter):
    """Gao, Lanchantin, Soffa, Qi.

    Black-box Generation of Adversarial Text Sequences to Evade Deep
    Learning Classifiers.

    https://arxiv.org/abs/1801.04354
    """

    def __init__(
            self, use_all_transformations=True, **kwargs
    ):
        from textattack.constraints.overlap import LevenshteinEditDistance
        from textattack.constraints.pre_transformation import (
            RepeatModification,
            StopwordModification,
        )
        from textattack.transformations import (
            CompositeTransformation,
            WordSwapNeighboringCharacterSwap,
            WordSwapRandomCharacterDeletion,
            WordSwapRandomCharacterInsertion,
            WordSwapRandomCharacterSubstitution,
        )

        if use_all_transformations:
            # We propose four similar methods:
            transformation = CompositeTransformation(
                [
                    # (1) Swap: Swap two adjacent letters in the word.
                    WordSwapNeighboringCharacterSwap(),
                    # (2) Substitution: Substitute a letter in the word with a random letter.
                    WordSwapRandomCharacterSubstitution(),
                    # (3) Deletion: Delete a random letter from the word.
                    WordSwapRandomCharacterDeletion(),
                    # (4) Insertion: Insert a random letter in the word.
                    WordSwapRandomCharacterInsertion(),
                ]
            )
        else:
            # We use the Combined Score and the Substitution Transformer to generate
            # adversarial samples, with the maximum edit distance difference of 30
            # (ϵ = 30).
            transformation = WordSwapRandomCharacterSubstitution()

        use_constraint = LevenshteinEditDistance(30)
        #
        constraints = [RepeatModification(), StopwordModification()] + [use_constraint]

        super().__init__(transformation, constraints=constraints, **kwargs)


class BackTranslationAugmenter(Augmenter):
    """Sentence level augmentation that uses MarianMTModel to back-translate.

    https://huggingface.co/transformers/model_doc/marian.html
    """

    def __init__(self, **kwargs):
        from textattack.transformations.sentence_transformations import BackTranslation

        transformation = BackTranslation(chained_back_translation=5)
        super().__init__(transformation, **kwargs)
