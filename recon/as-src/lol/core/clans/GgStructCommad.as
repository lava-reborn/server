class lol.core.clans.GgStructCommad
{
   var _act;
   var _date;
   var _id;
   var _name;
   var _perm;
   var _post;
   function GgStructCommad(obj)
   {
      this._id = obj.id;
      this._act = obj.act;
      this._name = obj.name;
      this._post = obj.post;
      this._date = obj.date;
      this._perm = obj.perm;
   }
   function get id()
   {
      return this._id;
   }
   function get act()
   {
      return this._act;
   }
   function get name()
   {
      return this._name;
   }
   function get post()
   {
      return this._post;
   }
   function get date()
   {
      return this._date;
   }
   function get perm()
   {
      return this._perm;
   }
}
