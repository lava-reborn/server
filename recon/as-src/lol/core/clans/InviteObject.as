class lol.core.clans.InviteObject
{
   var _pos;
   var _rec;
   var _soc;
   function InviteObject(obj)
   {
      this._rec = obj.rec;
      this._soc = obj.soc;
      this._pos = obj.pos;
   }
   function get rec()
   {
      return this._rec;
   }
   function get soc()
   {
      return this._soc;
   }
   function get pos()
   {
      return this._pos;
   }
}
