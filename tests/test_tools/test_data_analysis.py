"""Tests for the Data Analysis Tool."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any

from core.tools.data_analysis import (
    analyze_data,
    _descriptive_analysis,
    _correlation_analysis,
    _hypothesis_test,
    _time_series_analysis,
    _clustering_analysis,
    _feature_importance_analysis,
    _distribution_analysis,
    _outlier_analysis
)

@pytest.fixture
def sample_numeric_data():
    """
    Generates a DataFrame with three numeric columns for testing purposes.
    
    Returns:
        pd.DataFrame: A DataFrame with columns 'A', 'B', and 'C', each containing 100
        randomly generated numeric values from normal and exponential distributions.
    """
    np.random.seed(42)
    return pd.DataFrame({
        'A': np.random.normal(0, 1, 100),
        'B': np.random.normal(2, 1.5, 100),
        'C': np.random.exponential(2, 100)
    })

@pytest.fixture
def sample_categorical_data():
    """
    Generates a sample DataFrame with categorical and numeric columns for testing.
    
    Returns:
        pd.DataFrame: A DataFrame with a 'category' column containing repeated categories
        and a 'value' column of normally distributed random numbers.
    """
    return pd.DataFrame({
        'category': ['A', 'B', 'A', 'C', 'B'] * 20,
        'value': np.random.normal(0, 1, 100)
    })

@pytest.fixture
def sample_time_series_data():
    """
    Generates a sample time series DataFrame with dates and noisy sinusoidal values.
    
    Returns:
        pd.DataFrame: A DataFrame with a 'date' column of 100 consecutive days starting from 2023-01-01 and a 'value' column containing a sinusoidal signal with added Gaussian noise.
    """
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    return pd.DataFrame({
        'date': dates,
        'value': np.sin(np.linspace(0, 4*np.pi, 100)) + np.random.normal(0, 0.1, 100)
    })

def test_analyze_data_descriptive(sample_numeric_data):
    """
    Tests that the descriptive analysis returns summary statistics, skewness, quartiles, and correct row and column counts for numeric data.
    """
    result = analyze_data(
        sample_numeric_data.to_dict(),
        'descriptive',
        {'include_quartiles': True}
    )
    
    assert result['numeric']['summary'] is not None
    assert result['numeric']['skewness'] is not None
    assert result['numeric']['quartiles'] is not None
    assert result['row_count'] == 100
    assert result['column_count'] == 3

def test_analyze_data_correlation(sample_numeric_data):
    """
    Tests that correlation analysis returns a correlation matrix, method, and p-values when using Pearson correlation on numeric data.
    """
    result = analyze_data(
        sample_numeric_data.to_dict(),
        'correlation',
        {'method': 'pearson', 'include_pvalues': True}
    )
    
    assert result['correlation_matrix'] is not None
    assert result['method'] == 'pearson'
    assert result['pvalues'] is not None

def test_analyze_data_hypothesis_test(sample_categorical_data):
    """
    Tests the hypothesis testing analysis using ANOVA on categorical data.
    
    Verifies that the result includes the test type, test statistic, p-value, and group information.
    """
    result = analyze_data(
        sample_categorical_data.to_dict(),
        'hypothesis_test',
        {
            'test_type': 'anova',
            'group_column': 'category',
            'value_column': 'value'
        }
    )
    
    assert result['test_type'] == 'anova'
    assert 'statistic' in result
    assert 'pvalue' in result
    assert 'groups' in result

def test_analyze_data_time_series(sample_time_series_data):
    """
    Tests the time series analysis functionality of the analyze_data function.
    
    Verifies that the result includes total periods, start and end dates, rolling statistics,
    and that the rolling window size is correctly set to 7.
    """
    result = analyze_data(
        sample_time_series_data.to_dict(),
        'time_series',
        {
            'time_column': 'date',
            'value_column': 'value',
            'include_rolling_stats': True,
            'rolling_window': 7
        }
    )
    
    assert 'total_periods' in result
    assert 'start_date' in result
    assert 'end_date' in result
    assert 'rolling_stats' in result
    assert result['rolling_stats']['window'] == 7

def test_analyze_data_clustering(sample_numeric_data):
    """
    Tests the clustering analysis functionality of the analyze_data function.
    
    Verifies that clustering with k-means produces the expected method, number of clusters,
    cluster labels, and cluster statistics in the result.
    """
    result = analyze_data(
        sample_numeric_data.to_dict(),
        'clustering',
        {
            'method': 'kmeans',
            'n_clusters': 3
        }
    )
    
    assert result['method'] == 'kmeans'
    assert result['n_clusters'] == 3
    assert 'labels' in result
    assert 'cluster_stats' in result

def test_analyze_data_feature_importance(sample_numeric_data):
    """
    Tests feature importance analysis by verifying the presence and correctness of feature importance scores and model type in the result when a target column is provided.
    """
    # Add target column
    data = sample_numeric_data.copy()
    data['target'] = data['A'] * 0.3 + data['B'] * 0.5 + data['C'] * 0.2 + np.random.normal(0, 0.1, 100)
    
    result = analyze_data(
        data.to_dict(),
        'feature_importance',
        {'target_column': 'target'}
    )
    
    assert 'feature_importance' in result
    assert 'model_type' in result
    assert len(result['feature_importance']) == 3

def test_analyze_data_distribution(sample_numeric_data):
    """Test distribution analysis."""
    result = analyze_data(
        sample_numeric_data.to_dict(),
        'distribution',
        {'columns': ['A', 'B']}
    )
    
    assert 'distributions' in result
    assert 'A' in result['distributions']
    assert 'B' in result['distributions']
    for col in ['A', 'B']:
        assert 'mean' in result['distributions'][col]
        assert 'median' in result['distributions'][col]
        assert 'normality_test' in result['distributions'][col]
        assert 'percentiles' in result['distributions'][col]

def test_analyze_data_outliers(sample_numeric_data):
    """
    Tests the outlier detection analysis using the IQR method on specified numeric columns.
    
    Verifies that the result includes outlier statistics for columns 'A' and 'B', including method, threshold, outlier count, and outlier percentage.
    """
    result = analyze_data(
        sample_numeric_data.to_dict(),
        'outliers',
        {
            'method': 'iqr',
            'threshold': 1.5,
            'columns': ['A', 'B']
        }
    )
    
    assert 'outliers' in result
    assert 'A' in result['outliers']
    assert 'B' in result['outliers']
    for col in ['A', 'B']:
        assert 'method' in result['outliers'][col]
        assert 'threshold' in result['outliers'][col]
        assert 'outlier_count' in result['outliers'][col]
        assert 'outlier_percentage' in result['outliers'][col]

def test_analyze_data_invalid_input():
    """
    Tests that analyze_data returns an error when given an invalid JSON input string.
    """
    result = analyze_data(
        "invalid json",
        'descriptive'
    )
    assert 'error' in result
    assert result['error'] == 'Invalid JSON string'

def test_analyze_data_unsupported_analysis():
    """
    Tests that analyze_data returns an error when given an unsupported analysis type.
    
    Asserts that the result contains an error message indicating the analysis type is unsupported.
    """
    result = analyze_data(
        {'A': [1, 2, 3]},
        'unsupported_type'
    )
    assert 'error' in result
    assert 'Unsupported analysis type' in result['error']

def test_descriptive_analysis_empty_data():
    """Test descriptive analysis with empty data."""
    empty_df = pd.DataFrame()
    result = _descriptive_analysis(empty_df, {})
    assert result['row_count'] == 0
    assert result['column_count'] == 0

def test_correlation_analysis_single_column():
    """
    Tests that correlation analysis on a single-column DataFrame returns a correlation matrix containing the column.
    """
    single_col_df = pd.DataFrame({'A': [1, 2, 3]})
    result = _correlation_analysis(single_col_df, {'method': 'pearson'})
    assert result['correlation_matrix'] is not None
    assert 'A' in result['correlation_matrix']

def test_hypothesis_test_invalid_groups():
    """
    Tests that the hypothesis test function returns an error when only one group is present for a t-test.
    """
    df = pd.DataFrame({
        'group': ['A'] * 10,  # Only one group
        'value': range(10)
    })
    result = _hypothesis_test(df, {
        'test_type': 'ttest',
        'group_column': 'group',
        'value_column': 'value'
    })
    assert 'error' in result
    assert 'T-test requires exactly two groups' in result['error']

def test_time_series_analysis_invalid_date():
    """
    Tests that time series analysis returns an error when the date column contains invalid date strings.
    """
    df = pd.DataFrame({
        'date': ['invalid_date'] * 10,
        'value': range(10)
    })
    result = _time_series_analysis(df, {
        'time_column': 'date',
        'value_column': 'value'
    })
    assert 'error' in result

def test_clustering_analysis_invalid_method():
    """
    Tests that clustering analysis returns an error when an unsupported clustering method is specified.
    """
    df = pd.DataFrame({'A': range(10)})
    result = _clustering_analysis(df, {'method': 'invalid_method'})
    assert 'error' in result
    assert 'Unsupported clustering method' in result['error']

def test_feature_importance_no_target():
    """Test feature importance analysis without target column."""
    df = pd.DataFrame({'A': range(10)})
    result = _feature_importance_analysis(df, {})
    assert 'error' in result
    assert 'target_column must be specified' in result['error']

def test_distribution_analysis_insufficient_data():
    """
    Tests that distribution analysis handles columns with insufficient data points by omitting the normality test result.
    """
    df = pd.DataFrame({'A': [1, 2]})  # Too few points for normality test
    result = _distribution_analysis(df, {'columns': ['A']})
    assert 'distributions' in result
    assert 'A' in result['distributions']
    assert 'normality_test' not in result['distributions']['A']

def test_outlier_analysis_invalid_method():
    """Test outlier analysis with invalid method."""
    df = pd.DataFrame({'A': range(10)})
    result = _outlier_analysis(df, {
        'method': 'invalid_method',
        'columns': ['A']
    })
    assert 'error' in result
    assert 'Unsupported outlier detection method' in result['error'] 