"""Jupyter Notebook fixture generators for testing.

This module provides functions to generate various types of Jupyter Notebook
structures for comprehensive testing of the ipynb2markdown converter.

The generators create notebooks with different cell types, outputs, and
configurations to test edge cases and real-world scenarios.
"""

import json
from typing import Any, Dict


def create_simple_notebook() -> Dict[str, Any]:
    """Create a simple notebook with basic cell types.

    Returns
    -------
    dict
        A minimal notebook with markdown and code cells.
    """
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Simple Notebook\n", "This is a basic test notebook."]
            },
            {
                "cell_type": "code",
                "source": ["print('Hello, World!')"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["Hello, World!\n"]
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_notebook_with_images() -> Dict[str, Any]:
    """Create a notebook containing image outputs.

    Returns
    -------
    dict
        A notebook with cells that produce image outputs.
    """
    # Create a minimal 1x1 PNG image in base64
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Notebook with Images\n", "This notebook contains image outputs."]
            },
            {
                "cell_type": "code",
                "source": [
                    "import matplotlib.pyplot as plt\n",
                    "import numpy as np\n",
                    "\n",
                    "# Create a simple plot\n",
                    "x = np.linspace(0, 10, 100)\n",
                    "y = np.sin(x)\n",
                    "plt.figure(figsize=(8, 6))\n",
                    "plt.plot(x, y)\n",
                    "plt.title('Sine Wave')\n",
                    "plt.xlabel('x')\n",
                    "plt.ylabel('sin(x)')\n",
                    "plt.show()"
                ],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "image/png": png_data
                        }
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Multiple output formats\n",
                    "from PIL import Image\n",
                    "import io\n",
                    "img = Image.new('RGB', (50, 50), 'red')\n",
                    "img"
                ],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "execution_count": 2,
                        "data": {
                            "image/png": png_data,
                            "text/plain": ["<PIL.Image.Image image mode=RGB size=50x50>"]
                        }
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_notebook_with_long_outputs() -> Dict[str, Any]:
    """Create a notebook with very long outputs for testing truncation.

    Returns
    -------
    dict
        A notebook with cells producing extensive output.
    """
    long_output = [f"Line {i}: This is a very long output line with lots of text.\n" for i in range(50)]

    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Notebook with Long Outputs\n", "This notebook tests output truncation."]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Generate long output\n",
                    "for i in range(50):\n",
                    "    print(f'Line {i}: This is a very long output line with lots of text.')"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": long_output
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Multiple long outputs\n",
                    "import pandas as pd\n",
                    "import numpy as np\n",
                    "\n",
                    "# Create large dataframe\n",
                    "df = pd.DataFrame(np.random.randn(100, 5), columns=['A', 'B', 'C', 'D', 'E'])\n",
                    "df.head(20)"
                ],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {
                            "text/plain": [
                                "           A         B         C         D         E\n" +
                                "\n".join([
                                    (f"{i:2d}  {i * 0.1:8.6f}  {i * 0.2:8.6f}  "
                                     f"{i * 0.3:8.6f}  {i * 0.4:8.6f}  {i * 0.5:8.6f}")
                                    for i in range(20)
                                ])
                            ]
                        }
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_multi_language_notebook() -> Dict[str, Any]:
    """Create a notebook with cells in different programming languages.

    Returns
    -------
    dict
        A notebook with mixed language cells.
    """
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Multi-Language Notebook\n", "This notebook contains code in multiple languages."]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Python code\n",
                    "import numpy as np\n",
                    "arr = np.array([1, 2, 3, 4, 5])\n",
                    "print(f'Mean: {np.mean(arr)}')"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["Mean: 3.0\n"]
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "%%bash\n",
                    "# Shell commands\n",
                    "echo 'Running shell command'\n",
                    "ls -la | head -5"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Running shell command\n",
                            "total 1024\n",
                            "drwxr-xr-x  10 user  staff   320 Jan  1 12:00 .\n",
                            "drwxr-xr-x   5 user  staff   160 Jan  1 12:00 ..\n",
                            "-rw-r--r--   1 user  staff  1024 Jan  1 12:00 notebook.ipynb\n"
                        ]
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_notebook_with_errors() -> Dict[str, Any]:
    """Create a notebook with error outputs for testing error handling.

    Returns
    -------
    dict
        A notebook containing cells with error outputs.
    """
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Notebook with Errors\n", "This notebook contains error outputs."]
            },
            {
                "cell_type": "code",
                "source": [
                    "# This will cause an error\n",
                    "x = 1 / 0"
                ],
                "outputs": [
                    {
                        "output_type": "error",
                        "ename": "ZeroDivisionError",
                        "evalue": "division by zero",
                        "traceback": [
                            "---------------------------------------------------------------------------\n",
                            "ZeroDivisionError                         Traceback (most recent call last)\n",
                            "<ipython-input-1-9e1622b385b6> in <module>()\n",
                            "      1 # This will cause an error\n",
                            "----> 2 x = 1 / 0\n",
                            "\n",
                            "ZeroDivisionError: division by zero"
                        ]
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Successful code after error\n",
                    "try:\n",
                    "    result = 10 / 2\n",
                    "    print(f'Result: {result}')\n",
                    "except Exception as e:\n",
                    "    print(f'Error: {e}')"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["Result: 5.0\n"]
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_data_science_notebook() -> Dict[str, Any]:
    """Create a comprehensive data science notebook.

    Returns
    -------
    dict
        A realistic data science notebook with various cell types and outputs.
    """
    # Simple base64 encoded plot image
    plot_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": [
                    "# Customer Churn Analysis\n",
                    "\n",
                    "This notebook analyzes customer churn patterns using machine learning.\n",
                    "\n",
                    "## Table of Contents\n",
                    "\n",
                    "1. [Data Loading](#data-loading)\n",
                    "2. [Exploratory Data Analysis](#eda)\n",
                    "3. [Feature Engineering](#feature-engineering)\n",
                    "4. [Model Training](#model-training)\n",
                    "5. [Results](#results)\n"
                ]
            },
            {
                "cell_type": "markdown",
                "source": ["## Data Loading"]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Import required libraries\n",
                    "import pandas as pd\n",
                    "import numpy as np\n",
                    "import matplotlib.pyplot as plt\n",
                    "import seaborn as sns\n",
                    "from sklearn.model_selection import train_test_split\n",
                    "from sklearn.ensemble import RandomForestClassifier\n",
                    "from sklearn.metrics import classification_report, confusion_matrix\n",
                    "import warnings\n",
                    "warnings.filterwarnings('ignore')\n",
                    "\n",
                    "print(\"Libraries imported successfully!\")"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["Libraries imported successfully!\n"]
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Load the dataset\n",
                    "# Note: In real scenario, this would load from file\n",
                    "np.random.seed(42)\n",
                    "n_samples = 1000\n",
                    "\n",
                    "data = {\n",
                    "    'customer_id': range(1, n_samples + 1),\n",
                    "    'tenure': np.random.randint(1, 72, n_samples),\n",
                    "    'monthly_charges': np.random.uniform(20, 120, n_samples),\n",
                    "    'total_charges': np.random.uniform(100, 8000, n_samples),\n",
                    "    'contract': np.random.choice(['Month-to-month', 'One year', 'Two year'], n_samples),\n",
                    "    'churn': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])\n",
                    "}\n",
                    "\n",
                    "df = pd.DataFrame(data)\n",
                    "print(f\"Dataset shape: {df.shape}\")\n",
                    "print(f\"Churn rate: {df.churn.mean():.2%}\")\n",
                    "df.head()"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Dataset shape: (1000, 6)\n",
                            "Churn rate: 29.40%\n"
                        ]
                    },
                    {
                        "output_type": "execute_result",
                        "execution_count": 2,
                        "data": {
                            "text/plain": [
                                "   customer_id  tenure  monthly_charges  total_charges      contract  churn\n",
                                "0            1      38        64.327513    4375.351202  Month-to-month      0\n",
                                "1            2      26        77.259289    3527.849203      One year      1\n",
                                "2            3      47        58.245361    6180.432741      Two year      0\n",
                                "3            4      12        95.532416    2847.193827  Month-to-month      1\n",
                                "4            5       8        43.681024    1394.582039      One year      0"
                            ]
                        }
                    }
                ]
            },
            {
                "cell_type": "markdown",
                "source": ["## Exploratory Data Analysis"]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Basic statistics\n",
                    "print(\"Dataset Info:\")\n",
                    "print(df.info())\n",
                    "print(\"\\nDescriptive Statistics:\")\n",
                    "print(df.describe())"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Dataset Info:\n",
                            "<class 'pandas.core.frame.DataFrame'>\n",
                            "RangeIndex: 1000 entries, 0 to 999\n",
                            "Data columns (total 6 columns):\n",
                            " #   Column           Non-Null Count  Dtype  \n",
                            "---  ------           --------------  -----  \n",
                            " 0   customer_id      1000 non-null   int64  \n",
                            " 1   tenure           1000 non-null   int32  \n",
                            " 2   monthly_charges  1000 non-null   float64\n",
                            " 3   total_charges    1000 non-null   float64\n",
                            " 4   contract         1000 non-null   object \n",
                            " 5   churn            1000 non-null   int32  \n",
                            "dtypes: float64(2), int32(2), int64(1), object(1)\n",
                            "memory usage: 39.1+ KB\n",
                            "None\n",
                            "\n",
                            "Descriptive Statistics:\n",
                            "       customer_id      tenure  monthly_charges  total_charges       churn\n",
                            "count  1000.000000  1000.000000      1000.000000    1000.000000  1000.000000\n",
                            "mean    500.500000    35.854000        70.138234    4050.423891     0.294000\n",
                            "std     288.819436    20.619653        29.050512    2286.504419     0.455658\n",
                            "min       1.000000     1.000000        20.015894     100.238164     0.000000\n",
                            "25%     250.750000    18.000000        44.938297    2074.532532     0.000000\n",
                            "50%     500.500000    36.000000        70.389404    4039.284832     0.000000\n",
                            "75%     750.250000    53.000000        95.181165    6011.238495     1.000000\n",
                            "max    1000.000000    71.000000       119.936123    7998.652739     1.000000"
                        ]
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Visualization\n",
                    "plt.figure(figsize=(12, 8))\n",
                    "\n",
                    "plt.subplot(2, 2, 1)\n",
                    "df.tenure.hist(bins=30)\n",
                    "plt.title('Tenure Distribution')\n",
                    "plt.xlabel('Tenure (months)')\n",
                    "\n",
                    "plt.subplot(2, 2, 2)\n",
                    "df.groupby('churn').size().plot(kind='bar')\n",
                    "plt.title('Churn Distribution')\n",
                    "plt.xlabel('Churn (0=No, 1=Yes)')\n",
                    "\n",
                    "plt.subplot(2, 2, 3)\n",
                    "df.boxplot(column='monthly_charges', by='churn', ax=plt.gca())\n",
                    "plt.title('Monthly Charges by Churn')\n",
                    "\n",
                    "plt.subplot(2, 2, 4)\n",
                    "churn_by_contract = df.groupby(['contract', 'churn']).size().unstack()\n",
                    "churn_by_contract.plot(kind='bar', stacked=True, ax=plt.gca())\n",
                    "plt.title('Churn by Contract Type')\n",
                    "plt.xticks(rotation=45)\n",
                    "\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "image/png": plot_image
                        }
                    }
                ]
            },
            {
                "cell_type": "markdown",
                "source": ["## Model Training"]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Prepare features for modeling\n",
                    "from sklearn.preprocessing import LabelEncoder\n",
                    "\n",
                    "# Create a copy for modeling\n",
                    "model_df = df.copy()\n",
                    "\n",
                    "# Encode categorical variables\n",
                    "le = LabelEncoder()\n",
                    "model_df['contract_encoded'] = le.fit_transform(model_df['contract'])\n",
                    "\n",
                    "# Select features\n",
                    "features = ['tenure', 'monthly_charges', 'total_charges', 'contract_encoded']\n",
                    "X = model_df[features]\n",
                    "y = model_df['churn']\n",
                    "\n",
                    "# Split the data\n",
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n",
                    "\n",
                    "print(f\"Training set size: {X_train.shape[0]}\")\n",
                    "print(f\"Test set size: {X_test.shape[0]}\")"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Training set size: 800\n",
                            "Test set size: 200\n"
                        ]
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Train Random Forest model\n",
                    "rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)\n",
                    "rf_model.fit(X_train, y_train)\n",
                    "\n",
                    "# Make predictions\n",
                    "y_pred = rf_model.predict(X_test)\n",
                    "y_pred_proba = rf_model.predict_proba(X_test)[:, 1]\n",
                    "\n",
                    "# Calculate accuracy\n",
                    "from sklearn.metrics import accuracy_score\n",
                    "accuracy = accuracy_score(y_test, y_pred)\n",
                    "print(f\"Model Accuracy: {accuracy:.4f}\")\n",
                    "\n",
                    "# Feature importance\n",
                    "feature_importance = pd.DataFrame({\n",
                    "    'feature': features,\n",
                    "    'importance': rf_model.feature_importances_\n",
                    "}).sort_values('importance', ascending=False)\n",
                    "\n",
                    "print(\"\\nFeature Importance:\")\n",
                    "print(feature_importance)"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Model Accuracy: 0.7200\n",
                            "\n",
                            "Feature Importance:\n",
                            "           feature  importance\n",
                            "2    total_charges    0.412850\n",
                            "1  monthly_charges    0.298234\n",
                            "0           tenure    0.156891\n",
                            "3  contract_encoded    0.132025\n"
                        ]
                    }
                ]
            },
            {
                "cell_type": "markdown",
                "source": ["## Results"]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Detailed classification report\n",
                    "print(\"Classification Report:\")\n",
                    "print(classification_report(y_test, y_pred))\n",
                    "\n",
                    "# Confusion matrix\n",
                    "cm = confusion_matrix(y_test, y_pred)\n",
                    "print(\"\\nConfusion Matrix:\")\n",
                    "print(cm)\n",
                    "\n",
                    "# Plot confusion matrix\n",
                    "plt.figure(figsize=(8, 6))\n",
                    "sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', \n",
                    "            xticklabels=['No Churn', 'Churn'],\n",
                    "            yticklabels=['No Churn', 'Churn'])\n",
                    "plt.title('Confusion Matrix')\n",
                    "plt.ylabel('Actual')\n",
                    "plt.xlabel('Predicted')\n",
                    "plt.show()"
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [
                            "Classification Report:\n",
                            "              precision    recall  f1-score   support\n",
                            "\n",
                            "           0       0.74      0.86      0.79       140\n",
                            "           1       0.67      0.48      0.56        60\n",
                            "\n",
                            "    accuracy                           0.72       200\n",
                            "   macro avg       0.70      0.67      0.68       200\n",
                            "weighted avg       0.71      0.72      0.71       200\n",
                            "\n",
                            "\n",
                            "Confusion Matrix:\n",
                            "[[120  20]\n",
                            " [ 31  29]]\n"
                        ]
                    },
                    {
                        "output_type": "display_data",
                        "data": {
                            "image/png": plot_image
                        }
                    }
                ]
            },
            {
                "cell_type": "markdown",
                "source": [
                    "## Conclusions\n",
                    "\n",
                    "Based on our analysis:\n",
                    "\n",
                    "1. **Model Performance**: The Random Forest model achieved 72% accuracy on the test set.\n",
                    "\n",
                    "2. **Key Features**: The most important predictors of churn are:\n",
                    "   - Total charges (41.3% importance)\n",
                    "   - Monthly charges (29.8% importance)\n",
                    "   - Tenure (15.7% importance)\n",
                    "   - Contract type (13.2% importance)\n",
                    "\n",
                    "3. **Recommendations**:\n",
                    "   - Focus retention efforts on high-value customers (high total charges)\n",
                    "   - Consider pricing strategies for customers with high monthly charges\n",
                    "   - Implement early intervention for new customers (low tenure)\n",
                    "   - Encourage longer-term contracts to reduce churn\n",
                    "\n",
                    "4. **Next Steps**:\n",
                    "   - Collect additional features (customer satisfaction, support tickets, etc.)\n",
                    "   - Try other algorithms (XGBoost, Neural Networks)\n",
                    "   - Implement model in production for real-time scoring\n"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3",
                "display_name": "Python 3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.8.5"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def create_notebook_with_widgets() -> Dict[str, Any]:
    """Create a notebook with interactive widgets and rich outputs.

    Returns
    -------
    dict
        A notebook containing widget outputs and rich display elements.
    """
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Interactive Widgets Notebook\n", "This notebook demonstrates widget usage."]
            },
            {
                "cell_type": "code",
                "source": [
                    "import ipywidgets as widgets\n",
                    "from IPython.display import display, HTML, Markdown\n",
                    "\n",
                    "# Create interactive slider\n",
                    "slider = widgets.IntSlider(\n",
                    "    value=7,\n",
                    "    min=0,\n",
                    "    max=10,\n",
                    "    step=1,\n",
                    "    description='Test:'\n",
                    ")\n",
                    "display(slider)"
                ],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "application/vnd.jupyter.widget-view+json": {
                                "model_id": "abc123def456",
                                "version_major": 2,
                                "version_minor": 0
                            },
                            "text/plain": [
                                "IntSlider(value=7, description='Test:', max=10)"
                            ]
                        }
                    }
                ]
            },
            {
                "cell_type": "code",
                "source": [
                    "# Display rich HTML content\n",
                    "display(HTML('<h3 style=\"color: blue;\">Rich HTML Content</h3>'))\n",
                    "display(Markdown('**Bold markdown** and *italic* text.'))"
                ],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/html": ["<h3 style=\"color: blue;\">Rich HTML Content</h3>"],
                            "text/plain": ["<IPython.core.display.HTML object>"]
                        }
                    },
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/markdown": ["**Bold markdown** and *italic* text."],
                            "text/plain": ["<IPython.core.display.Markdown object>"]
                        }
                    }
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def save_notebook_to_file(notebook: Dict[str, Any], filepath: str) -> None:
    """Save a notebook dictionary to a .ipynb file.

    Parameters
    ----------
    notebook : dict
        The notebook structure to save.
    filepath : str
        The file path where to save the notebook.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)


# Convenience function to create all fixtures
def create_all_fixtures(output_dir: str = "test_notebooks") -> Dict[str, str]:
    """Create all notebook fixtures and save them to files.

    Parameters
    ----------
    output_dir : str, default "test_notebooks"
        Directory to save the generated notebooks.

    Returns
    -------
    dict
        Mapping of notebook names to their file paths.
    """
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    fixtures = {
        'simple': create_simple_notebook(),
        'with_images': create_notebook_with_images(),
        'long_outputs': create_notebook_with_long_outputs(),
        'multi_language': create_multi_language_notebook(),
        'with_errors': create_notebook_with_errors(),
        'data_science': create_data_science_notebook(),
        'with_widgets': create_notebook_with_widgets(),
    }

    file_paths = {}
    for name, notebook in fixtures.items():
        filepath = output_path / f"{name}.ipynb"
        save_notebook_to_file(notebook, str(filepath))
        file_paths[name] = str(filepath)

    return file_paths


if __name__ == "__main__":
    # Generate all fixtures when run as script
    paths = create_all_fixtures()
    print("Generated notebook fixtures:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
