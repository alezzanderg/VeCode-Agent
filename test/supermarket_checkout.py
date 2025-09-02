"""
Supermarket Checkout System
Handles scanning items, calculating totals, applying discounts, and processing payments.
"""

import json
from typing import Dict, List, Optional, Union


class Product:
    """Represents a product in the supermarket inventory."""
    
    def __init__(self, sku: str, name: str, price: float, unit: str = "each"):
        """
        Initialize a product.
        
        Args:
            sku: Stock Keeping Unit (unique identifier)
            name: Product name
            price: Price per unit
            unit: Unit of measurement (each, kg, liter, etc.)
        """
        self.sku = sku
        self.name = name
        self.price = price
        self.unit = unit
    
    def __repr__(self):
        return f"Product({self.sku}, '{self.name}', {self.price}, '{self.unit}')"


class Discount:
    """Represents a discount rule for products."""
    
    def __init__(self, sku: str, rule_type: str, **kwargs):
        """
        Initialize a discount rule.
        
        Args:
            sku: Product SKU this discount applies to
            rule_type: Type of discount ('buy_x_get_y', 'bulk', 'percentage')
            kwargs: Additional parameters based on rule_type
        """
        self.sku = sku
        self.rule_type = rule_type
        self.params = kwargs
    
    def calculate_discount(self, quantity: int, unit_price: float) -> float:
        """
        Calculate discount amount based on quantity and price.
        
        Args:
            quantity: Number of items
            unit_price: Price per item
            
        Returns:
            Discount amount
        """
        if self.rule_type == 'buy_x_get_y':
            buy_x = self.params.get('buy_x', 1)
            get_y = self.params.get('get_y', 0)
            if quantity >= buy_x:
                free_items = (quantity // (buy_x + get_y)) * get_y
                return free_items * unit_price
        
        elif self.rule_type == 'bulk':
            min_quantity = self.params.get('min_quantity', 0)
            discount_price = self.params.get('discount_price', unit_price)
            if quantity >= min_quantity:
                return (unit_price - discount_price) * quantity
        
        elif self.rule_type == 'percentage':
            percentage = self.params.get('percentage', 0)
            if quantity >= self.params.get('min_quantity', 0):
                return (unit_price * quantity * percentage) / 100
        
        return 0.0


class SupermarketCheckout:
    """Main checkout system class."""
    
    def __init__(self, inventory_file: Optional[str] = None):
        """
        Initialize checkout system.
        
        Args:
            inventory_file: Path to JSON file containing inventory data
        """
        self.products: Dict[str, Product] = {}
        self.discounts: Dict[str, Discount] = {}
        self.cart: Dict[str, int] = {}
        
        if inventory_file:
            self.load_inventory(inventory_file)
    
    def load_inventory(self, file_path: str) -> None:
        """
        Load products and discounts from a JSON file.
        
        Args:
            file_path: Path to JSON inventory file
            
        Raises:
            FileNotFoundError: If inventory file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load products
            for product_data in data.get('products', []):
                product = Product(
                    sku=product_data['sku'],
                    name=product_data['name'],
                    price=product_data['price'],
                    unit=product_data.get('unit', 'each')
                )
                self.products[product.sku] = product
            
            # Load discounts
            for discount_data in data.get('discounts', []):
                discount = Discount(
                    sku=discount_data['sku'],
                    rule_type=discount_data['rule_type'],
                    **discount_data.get('params', {})
                )
                self.discounts[discount.sku] = discount
                
        except FileNotFoundError:
            raise FileNotFoundError(f"Inventory file '{file_path}' not found")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in inventory file '{file_path}'")
    
    def scan_item(self, sku: str, quantity: int = 1) -> bool:
        """
        Scan an item and add it to the cart.
        
        Args:
            sku: Product SKU
            quantity: Number of items to add
            
        Returns:
            True if item was successfully scanned, False otherwise
        """
        if sku not in self.products:
            return False
            
        if sku in self.cart:
            self.cart[sku] += quantity
        else:
            self.cart[sku] = quantity
            
        return True