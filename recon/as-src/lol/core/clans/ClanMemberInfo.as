class lol.core.clans.ClanMemberInfo
{
   var _char;
   var _clanInfo;
   var _date;
   var _memberPost;
   var _name;
   var _online;
   var _rights;
   var _clanReg = 0;
   function ClanMemberInfo()
   {
      this._rights = new lol.core.clans.Rights();
      this._memberPost = "";
      this._clanInfo = new lol.core.clans.ClanInfo(0,"");
      this._char = 0;
      this._online = 0;
   }
   function initByFellowMessage(fellow)
   {
      this._rights = new lol.core.clans.Rights();
      this._rights.rightsCode = fellow.perm;
      this._memberPost = fellow.post;
      this._char = fellow.char;
      this._date = "";
      this.clanReg = fellow.reg;
   }
   function killByFellowMessage(fellow)
   {
      this._rights.rightsCode = null;
      this._memberPost = null;
      this._char = null;
      this._date = null;
      this.clanReg = fellow.reg;
      this.clanInfo = null;
   }
   function get rights()
   {
      return this._rights;
   }
   function set rights(value)
   {
      this._rights = value;
   }
   function get memberPost()
   {
      return this._memberPost;
   }
   function set memberPost(value)
   {
      this._memberPost = !value ? "" : value;
   }
   function get clanInfo()
   {
      return this._clanInfo;
   }
   function set clanInfo(value)
   {
      this._clanInfo = value;
   }
   function get char()
   {
      return this._char;
   }
   function set char(value)
   {
      this._char = value;
   }
   function get date()
   {
      return this._date;
   }
   function set date(value)
   {
      this._date = !value ? "" : value;
      var _loc8_;
      var _loc6_;
      var _loc5_;
      var _loc3_;
      var _loc4_;
      var _loc7_;
      var _loc2_;
      if(this._date != "")
      {
         _loc8_ = this._date.substring(0,4);
         _loc6_ = this._date.substring(5,7);
         _loc5_ = this._date.substring(8,10);
         _loc3_ = Number(this._date.substring(11,13));
         _loc4_ = this._date.substring(14,16);
         _loc7_ = this._date.substring(17,19);
         _loc2_ = new Date();
         _loc2_.setHours(_loc3_);
         _loc2_.setMinutes(_loc4_ - _loc2_.getTimezoneOffset());
         _loc3_ = _loc2_.getHours() >= 10 ? _loc2_.getHours() : "0" + _loc2_.getHours();
         _loc4_ = _loc2_.getMinutes() >= 10 ? _loc2_.getMinutes() : "0" + _loc2_.getMinutes();
         this._date = _loc8_ + "-" + _loc6_ + "-" + _loc5_ + " " + _loc3_ + ":" + _loc4_ + ":" + _loc7_;
      }
   }
   function get online()
   {
      return this._online;
   }
   function set online(value)
   {
      this._online = value;
   }
   function get name()
   {
      return this._name;
   }
   function set name(value)
   {
      this._name = value;
   }
   function get clanReg()
   {
      return this._clanReg;
   }
   function set clanReg(value)
   {
      this._clanReg = value;
   }
}
