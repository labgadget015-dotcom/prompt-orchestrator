"""Core orchestrator for prompt execution system."""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class ModuleResult:
    """Result container for module execution."""
    
    def __init__(self, output: Any, passed: bool, metrics: Dict[str, Any]):
        self.output = output
        self.passed = passed
        self.metrics = metrics
        self.timestamp = datetime.now()


class PromptOrchestrator:
    """Main orchestration engine for prompt workflows."""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.router = None
        self.modules = {}
        self.analytics = None
        self.execution_log = []
        
    def register_module(self, name: str, module):
        """Register a prompt module."""
        self.modules[name] = module
        
    def execute(self, task: str, context: Optional[Dict] = None) -> ModuleResult:
        """Execute a task through the orchestrated chain."""
        context = context or {}
        
        # Route to appropriate chain
        chain = self.router.select_chain(task, context) if self.router else self._default_chain()
        
        # Execute chain
        result = task
        chain_log = []
        
        for module_name in chain:
            if module_name not in self.modules:
                raise ValueError(f"Module '{module_name}' not registered")
                
            module = self.modules[module_name]
            result = module.run(self.llm, result, context)
            
            # Log execution
            chain_log.append({
                'module': module_name,
                'passed': result.passed,
                'metrics': result.metrics,
                'timestamp': result.timestamp.isoformat()
            })
            
            # Analytics tracking
            if self.analytics:
                self.analytics.log(module_name, result.metrics)
            
            # Hard stop on failure
            if not result.passed:
                return self._handle_failure(module_name, result, chain_log)
        
        self.execution_log.append(chain_log)
        return result
    
    def _default_chain(self) -> List[str]:
        """Default execution chain if no router configured."""
        return ['verification']
    
    def _handle_failure(self, module_name: str, result: ModuleResult, chain_log: List[Dict]) -> ModuleResult:
        """Handle module failure."""
        self.execution_log.append(chain_log)
        return ModuleResult(
            output=f"Failed at {module_name}: {result.output}",
            passed=False,
            metrics={'error': module_name, 'log': chain_log}
        )
