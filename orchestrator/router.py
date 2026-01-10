"""Intelligent routing for prompt chains."""

from typing import List, Dict, Any
import re


class PromptRouter:
    """Routes tasks to appropriate module chains based on analysis."""
    
    def __init__(self):
        self.chain_patterns = {
            'analysis': ['golden', 'domain', 'cot', 'verification', 'bias'],
            'creative': ['domain', 'synthesizer', 'verification', 'bias'],
            'validation': ['cot', 'verification', 'bias'],
            'optimization': ['golden', 'cot', 'domain', 'feedback', 'verification'],
            'simple': ['cot', 'verification']
        }
        
        self.keywords = {
            'analysis': ['analyze', 'evaluate', 'assess', 'review', 'examine', 'study'],
            'creative': ['create', 'generate', 'design', 'build', 'develop', 'compose'],
            'validation': ['verify', 'check', 'validate', 'test', 'confirm'],
            'optimization': ['optimize', 'improve', 'enhance', 'refine', 'tune', 'revenue'],
        }
    
    def select_chain(self, task: str, context: Dict[str, Any] = None) -> List[str]:
        """Select appropriate chain based on task content."""
        context = context or {}
        
        # Override from context if specified
        if 'chain' in context:
            return context['chain']
        
        # Analyze task to determine chain
        task_lower = task.lower()
        scores = {}
        
        for chain_type, keywords in self.keywords.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[chain_type] = score
        
        # Select highest scoring chain
        if scores:
            selected = max(scores, key=scores.get)
            return self.chain_patterns[selected]
        
        # Default to simple chain
        return self.chain_patterns['simple']
    
    def register_chain(self, name: str, modules: List[str]):
        """Register a custom chain pattern."""
        self.chain_patterns[name] = modules
    
    def register_keywords(self, chain_type: str, keywords: List[str]):
        """Register keywords for chain selection."""
        if chain_type not in self.keywords:
            self.keywords[chain_type] = []
        self.keywords[chain_type].extend(keywords)
