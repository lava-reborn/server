class lol.utils.SCString
{
   var _id;
   var _string;
   function SCString(__id, str)
   {
      this._id = __id;
      this._string = str;
   }
   function get id()
   {
      return this._id;
   }
   function set id(__id)
   {
      this._id = __id;
   }
   function get string()
   {
      return this._string;
   }
   function set string(__string)
   {
      this._string = __string;
   }
}
