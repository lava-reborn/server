class lol.local.SDBItem
{
   var _name;
   var _resource;
   var _rootID;
   var _typeID;
   function SDBItem(type_id, root_id, item_name, res)
   {
      this._typeID = type_id;
      this._rootID = root_id;
      this._name = item_name;
      this._resource = res;
   }
   function get name()
   {
      return this._name;
   }
   function get typeID()
   {
      return this._typeID;
   }
   function get rootID()
   {
      return this._rootID;
   }
   function get resource()
   {
      return this._resource;
   }
}
