class HRAgentException(Exception):
    """Base exception for the HR Agent application."""
    pass

class FileProcessingError(HRAgentException):
    """Raised when resume extraction fails."""
    pass

class WorkflowStateError(HRAgentException):
    """Raised when the LangGraph state is invalid or missing."""
    pass

class ValidationException(HRAgentException):
    """Raised when input validation fails."""
    pass