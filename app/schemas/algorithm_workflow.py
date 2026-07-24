"""
Typed models for the xyflow-based algorithm `formula` / `calculation_steps`
structure (see app/schemas/bop_umbrella_algorithm_mongoimport.json).

`AlgorithmCreateSchema.formula` and `.calculation_steps` in algorithm.py are
intentionally loose (Dict[str, Any]) so the API accepts any workflow shape.
Use `Formula` / `CalculationStep` here when you want to validate or build a
workflow document with real type checking instead.
"""

from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "straight"
    selectable: bool = True
    focusable: bool = True


class Formula(BaseModel):
    expression: str = ""
    description: Optional[str] = None
    workflowEdges: List[WorkflowEdge] = Field(default_factory=list)


# --- Step 1: data_intake ---------------------------------------------------

class IntakeField(BaseModel):
    question: str
    variableName: str
    dataType: Literal["number", "string", "boolean"]
    inputControl: Literal["input", "dropdown"]
    options: str = ""
    required: bool = False
    visibleWhen: str = ""
    disabledWhen: str = ""


class DataIntakeStepData(BaseModel):
    stepType: Literal["data_intake"]
    label: str
    collapsed: bool = True
    stepOrder: int
    intakes: List[IntakeField] = Field(default_factory=list)


# --- Step 2: rating_table_lookup -------------------------------------------

class FieldMapping(BaseModel):
    tableField: str = ""
    variableName: str = ""
    valueSource: Literal["literal", "variable"]
    compareOperator: Literal["eq", "lte", "gte", "lt", "gt", "ne"] = "eq"
    literalValue: Optional[str] = None
    combineWith: Optional[Literal["AND", "OR"]] = None


class Lookup(BaseModel):
    tableName: str
    fieldMappings: List[FieldMapping] = Field(default_factory=list)
    outputField: str
    interpolationMode: Literal["exact", "range", "nearest"] = "exact"
    outputVariable: str
    runCondition: Optional[str] = None


class RatingTableLookupStepData(BaseModel):
    stepType: Literal["rating_table_lookup"]
    label: str
    collapsed: bool = True
    stepOrder: int
    lookups: List[Lookup] = Field(default_factory=list)


# --- Step 3: expression ------------------------------------------------------

class Expression(BaseModel):
    expression: str
    outputVariable: str
    runCondition: Optional[str] = None


class ExpressionStepData(BaseModel):
    stepType: Literal["expression"]
    label: str
    collapsed: bool = True
    stepOrder: int
    expressions: List[Expression] = Field(default_factory=list)


# --- Step 4: quote_output ----------------------------------------------------

class OutputExpression(BaseModel):
    expression: str
    formatTemplate: str = ""


class QuoteOutputStepData(BaseModel):
    stepType: Literal["quote_output"]
    label: str
    collapsed: bool = True
    stepOrder: int
    outputs: List[OutputExpression] = Field(default_factory=list)


# --- Calculation step wrapper ------------------------------------------------

StepData = Union[
    DataIntakeStepData,
    RatingTableLookupStepData,
    ExpressionStepData,
    QuoteOutputStepData,
]


class CalculationStep(BaseModel):
    id: str
    type: Literal["data_intake", "rating_table_lookup", "expression", "quote_output"]
    label: str
    data: StepData = Field(discriminator="stepType")
    position: Position
