class lol.core.clans.FellowCommand
{
   var _char;
   var _id;
   var _perm;
   var _post;
   var _reg;
   var _soc;
   var _stand;
   function FellowCommand(obj)
   {
      this._id = obj.id;
      this._reg = obj.reg;
      this._soc = obj.soc;
      this._post = obj.post;
      this._stand = obj.stand;
      this._char = obj.char;
      this._perm = obj.perm;
   }
   function get id()
   {
      return this._id;
   }
   function get reg()
   {
      return this._reg;
   }
   function get soc()
   {
      return this._soc;
   }
   function get post()
   {
      return this._post;
   }
   function get stand()
   {
      return this._stand;
   }
   function get char()
   {
      return this._char;
   }
   function get perm()
   {
      return this._perm;
   }
}
