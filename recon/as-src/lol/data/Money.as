class lol.data.Money
{
   var _type;
   var _value;
   static var AFRO = "afro";
   static var GOLD = "gold";
   function Money(val, mType)
   {
      this._value = val;
      this._type = mType;
   }
   function get moneyValue()
   {
      return this._value;
   }
   function set moneyValue(val)
   {
      this._value = val;
   }
   function get moneyType()
   {
      return this._type;
   }
   function set moneyType(mType)
   {
      this._type = mType;
   }
   function toString()
   {
      return String(this._value);
   }
   function defeatEvil()
   {
   }
}
