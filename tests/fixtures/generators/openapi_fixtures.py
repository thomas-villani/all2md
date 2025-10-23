"""OpenAPI/Swagger test fixture generators for testing OpenAPI conversion.

This module provides functions to programmatically create OpenAPI specifications
for testing various aspects of OpenAPI parsing.
"""

import json
from io import BytesIO


def create_simple_openapi() -> str:
    """Create a simple OpenAPI spec for basic testing.

    Returns
    -------
    str
        Simple OpenAPI specification as YAML string.

    """
    spec = """openapi: 3.0.0
info:
  title: Simple API
  version: 1.0.0

paths:
  /items:
    get:
      summary: Get items
      responses:
        '200':
          description: Success
"""
    return spec


def create_openapi_with_servers() -> str:
    """Create OpenAPI spec with server definitions.

    Returns
    -------
    str
        OpenAPI specification with servers section.

    """
    spec = """openapi: 3.0.0
info:
  title: API with Servers
  version: 1.0.0

servers:
  - url: https://api.example.com/v1
    description: Production server
  - url: https://staging.example.com/v1
    description: Staging server

paths:
  /test:
    get:
      summary: Test endpoint
      responses:
        '200':
          description: Success
"""
    return spec


def create_openapi_with_parameters() -> str:
    """Create OpenAPI spec with various parameter types.

    Returns
    -------
    str
        OpenAPI specification with parameters.

    """
    spec = """openapi: 3.0.0
info:
  title: Parameters API
  version: 1.0.0

paths:
  /users/{userId}:
    get:
      summary: Get user by ID
      parameters:
        - name: userId
          in: path
          required: true
          schema:
            type: integer
        - name: fields
          in: query
          description: Fields to include
          schema:
            type: string
        - name: X-API-Key
          in: header
          required: true
          schema:
            type: string
      responses:
        '200':
          description: User found
"""
    return spec


def create_openapi_with_request_body() -> str:
    """Create OpenAPI spec with request body examples.

    Returns
    -------
    str
        OpenAPI specification with request bodies.

    """
    spec = """openapi: 3.0.0
info:
  title: Request Body API
  version: 1.0.0

paths:
  /users:
    post:
      summary: Create user
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                email:
                  type: string
            example:
              name: John Doe
              email: john@example.com
      responses:
        '201':
          description: User created
"""
    return spec


def create_openapi_with_tags() -> str:
    """Create OpenAPI spec with tags for grouping.

    Returns
    -------
    str
        OpenAPI specification with tags.

    """
    spec = """openapi: 3.0.0
info:
  title: Tagged API
  version: 1.0.0

tags:
  - name: users
    description: User operations
  - name: products
    description: Product operations

paths:
  /users:
    get:
      tags:
        - users
      summary: List users
      responses:
        '200':
          description: Success
  /products:
    get:
      tags:
        - products
      summary: List products
      responses:
        '200':
          description: Success
"""
    return spec


def create_openapi_with_schemas() -> str:
    """Create OpenAPI spec with component schemas.

    Returns
    -------
    str
        OpenAPI specification with schemas.

    """
    spec = """openapi: 3.0.0
info:
  title: Schemas API
  version: 1.0.0

paths:
  /users:
    get:
      responses:
        '200':
          description: Users
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/User'

components:
  schemas:
    User:
      type: object
      required:
        - id
        - name
      properties:
        id:
          type: integer
          format: int64
          description: User ID
        name:
          type: string
          description: User name
        email:
          type: string
          description: User email
        role:
          type: string
          enum:
            - admin
            - user
            - guest
"""
    return spec


def create_swagger_2_spec() -> str:
    """Create Swagger 2.0 specification.

    Returns
    -------
    str
        Swagger 2.0 specification as YAML string.

    """
    spec = """swagger: '2.0'
info:
  title: Swagger 2.0 API
  version: 1.0.0

host: api.example.com
basePath: /v1
schemes:
  - https

paths:
  /items:
    get:
      summary: Get items
      produces:
        - application/json
      responses:
        '200':
          description: Success
          schema:
            type: array
            items:
              $ref: '#/definitions/Item'

definitions:
  Item:
    type: object
    properties:
      id:
        type: integer
      name:
        type: string
"""
    return spec


def create_openapi_complex() -> str:
    """Create a complex OpenAPI spec with multiple features.

    Returns
    -------
    str
        Complex OpenAPI specification.

    """
    spec = """openapi: 3.0.0
info:
  title: E-Commerce API
  description: A comprehensive e-commerce API
  version: 2.0.0
  contact:
    name: API Team
    email: api@example.com
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html

servers:
  - url: https://api.shop.com/v2
    description: Production
  - url: https://sandbox.shop.com/v2
    description: Sandbox

tags:
  - name: products
    description: Product catalog
  - name: orders
    description: Order management

paths:
  /products:
    get:
      summary: List products
      tags:
        - products
      parameters:
        - name: category
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: Product list
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Product'

  /orders:
    post:
      summary: Create order
      tags:
        - orders
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Order'
            example:
              items:
                - productId: 123
                  quantity: 2
      responses:
        '201':
          description: Order created
        '400':
          description: Invalid request

components:
  schemas:
    Product:
      type: object
      required:
        - id
        - name
        - price
      properties:
        id:
          type: integer
          format: int64
        name:
          type: string
        price:
          type: number
          format: double
        category:
          type: string

    Order:
      type: object
      required:
        - items
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/OrderItem'

    OrderItem:
      type: object
      properties:
        productId:
          type: integer
        quantity:
          type: integer
"""
    return spec


def create_openapi_with_deprecated() -> str:
    """Create OpenAPI spec with deprecated operations.

    Returns
    -------
    str
        OpenAPI specification with deprecated operations.

    """
    spec = """openapi: 3.0.0
info:
  title: API with Deprecated Operations
  version: 1.0.0

paths:
  /legacy:
    get:
      summary: Legacy endpoint
      deprecated: true
      responses:
        '200':
          description: Success

  /current:
    get:
      summary: Current endpoint
      responses:
        '200':
          description: Success
"""
    return spec


def openapi_bytes_io(spec_str: str) -> BytesIO:
    """Convert OpenAPI spec string to BytesIO.

    Parameters
    ----------
    spec_str : str
        OpenAPI specification string

    Returns
    -------
    BytesIO
        BytesIO containing the spec

    """
    return BytesIO(spec_str.encode("utf-8"))


def openapi_json_bytes_io(spec_yaml: str) -> BytesIO:
    """Convert OpenAPI YAML to JSON BytesIO.

    Parameters
    ----------
    spec_yaml : str
        OpenAPI specification as YAML string

    Returns
    -------
    BytesIO
        BytesIO containing JSON version of spec

    """
    import yaml

    data = yaml.safe_load(spec_yaml)
    json_str = json.dumps(data, indent=2)
    return BytesIO(json_str.encode("utf-8"))
