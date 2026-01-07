# MCP Tools List - Ratings API

This document lists all available MCP tools exposed by the Ratings API MCP server.

## Total Tools: 45

### Companies (5 tools)
1. **get_companies** - Get a list of companies with optional filtering and pagination
   - Parameters: `skip`, `limit`, `active`, `company_name`
   
2. **get_company** - Get a specific company by ID
   - Parameters: `company_id` (int)
   
3. **create_company** - Create a new company
   - Parameters: `company_data` (dict)
   
4. **update_company** - Update an existing company
   - Parameters: `company_id` (int), `company_data` (dict)
   
5. **delete_company** - Delete a company by ID
   - Parameters: `company_id` (int)

### LOBs - Lines of Business (5 tools)
6. **get_lobs** - Get a list of lines of business with optional filtering and pagination
   - Parameters: `skip`, `limit`, `active`, `lob_name`
   
7. **get_lob** - Get a specific line of business by ID
   - Parameters: `lob_id` (int)
   
8. **create_lob** - Create a new line of business
   - Parameters: `lob_data` (dict)
   
9. **update_lob** - Update an existing line of business
   - Parameters: `lob_id` (int), `lob_data` (dict)
   
10. **delete_lob** - Delete a line of business by ID
    - Parameters: `lob_id` (int)

### Products (5 tools)
11. **get_products** - Get a list of products with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `product_name`
    
12. **get_product** - Get a specific product by ID
    - Parameters: `product_id` (int)
    
13. **create_product** - Create a new product
    - Parameters: `product_data` (dict)
    
14. **update_product** - Update an existing product
    - Parameters: `product_id` (int), `product_data` (dict)
    
15. **delete_product** - Delete a product by ID
    - Parameters: `product_id` (int)

### States (5 tools)
16. **get_states** - Get a list of states with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `state_name`
    
17. **get_state** - Get a specific state by ID
    - Parameters: `state_id` (int)
    
18. **create_state** - Create a new state
    - Parameters: `state_data` (dict)
    
19. **update_state** - Update an existing state
    - Parameters: `state_id` (int), `state_data` (dict)
    
20. **delete_state** - Delete a state by ID
    - Parameters: `state_id` (int)

### Contexts (5 tools)
21. **get_contexts** - Get a list of contexts with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `context_name`
    
22. **get_context** - Get a specific context by ID
    - Parameters: `context_id` (int)
    
23. **create_context** - Create a new context
    - Parameters: `context_data` (dict)
    
24. **update_context** - Update an existing context
    - Parameters: `context_id` (int), `context_data` (dict)
    
25. **delete_context** - Delete a context by ID
    - Parameters: `context_id` (int)

### Rating Tables (5 tools)
26. **get_ratingtables** - Get a list of rating tables with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `table_name`, `table_type`, `company_id`, `lob_id`, `state_id`, `product_id`, `context_id`
    
27. **get_ratingtable** - Get a specific rating table by ID
    - Parameters: `ratingtable_id` (int)
    
28. **create_ratingtable** - Create a new rating table
    - Parameters: `ratingtable_data` (dict)
    
29. **update_ratingtable** - Update an existing rating table
    - Parameters: `ratingtable_id` (int), `ratingtable_data` (dict)
    
30. **delete_ratingtable** - Delete a rating table by ID
    - Parameters: `ratingtable_id` (int)

### Algorithms (5 tools)
31. **get_algorithms** - Get a list of algorithms with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `algorithm_name`, `company_id`, `lob_id`, `state_id`, `product_id`
    
32. **get_algorithm** - Get a specific algorithm by ID
    - Parameters: `algorithm_id` (int)
    
33. **create_algorithm** - Create a new algorithm
    - Parameters: `algorithm_data` (dict)
    
34. **update_algorithm** - Update an existing algorithm
    - Parameters: `algorithm_id` (int), `algorithm_data` (dict)
    
35. **delete_algorithm** - Delete an algorithm by ID
    - Parameters: `algorithm_id` (int)

### Rating Manuals (5 tools)
36. **get_ratingmanuals** - Get a list of rating manuals with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `manual_name`, `company_id`, `lob_id`, `state_id`, `product_id`, `ratingtable_id`, `effective_date`
    
37. **get_ratingmanual** - Get a specific rating manual by ID
    - Parameters: `ratingmanual_id` (int)
    
38. **create_ratingmanual** - Create a new rating manual
    - Parameters: `ratingmanual_data` (dict)
    
39. **update_ratingmanual** - Update an existing rating manual
    - Parameters: `ratingmanual_id` (int), `ratingmanual_data` (dict)
    
40. **delete_ratingmanual** - Delete a rating manual by ID
    - Parameters: `ratingmanual_id` (int)

### Rating Plans (5 tools)
41. **get_ratingplans** - Get a list of rating plans with optional filtering and pagination
    - Parameters: `skip`, `limit`, `active`, `plan_name`, `company_id`, `lob_id`, `state_id`, `product_id`, `algorithm_id`, `effective_date`
    
42. **get_ratingplan** - Get a specific rating plan by ID
    - Parameters: `ratingplan_id` (int)
    
43. **create_ratingplan** - Create a new rating plan
    - Parameters: `ratingplan_data` (dict)
    
44. **update_ratingplan** - Update an existing rating plan
    - Parameters: `ratingplan_id` (int), `ratingplan_data` (dict)
    
45. **delete_ratingplan** - Delete a rating plan by ID
    - Parameters: `ratingplan_id` (int)

### Health Check (1 tool)
46. **health_check** - Check the health status of the API and database
    - Parameters: None

## Accessing Tools

### Via HTTP API
```bash
# List all tools
GET /api/v1/mcp/tools

# Call a tool
POST /api/v1/mcp/tools/{tool_name}/call
Body: {"param1": value1, "param2": value2, ...}
```

### Via MCP Protocol (Cursor)
Once configured in Cursor, you can use these tools directly in prompts:
- "Get all companies"
- "Create a new rating table"
- "List all active algorithms"
- "Find rating manuals for company 100000001"

## Example Usage in Cursor

Once the MCP server is configured in Cursor, you can use natural language prompts:

```
"Get all companies with active=true"
"Create a new company with name 'Acme Corp'"
"List all rating tables for company_id 100000001"
"Get rating manual with ID 100000001"
"Check the health of the API"
```

Cursor will automatically use the appropriate MCP tools to fulfill these requests.







