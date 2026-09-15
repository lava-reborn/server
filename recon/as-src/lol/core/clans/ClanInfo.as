class lol.core.clans.ClanInfo
{
   var _clanName;
   var _memberList;
   var _reg;
   var _standingArray;
   function ClanInfo(tReg, tClanName)
   {
      this._reg = tReg;
      this._clanName = tClanName;
   }
   function updateClanMember(entity)
   {
      this._memberList[entity.id] = entity;
      return this._memberList;
   }
   function updateClanMemberList()
   {
   }
   function get reg()
   {
      return this._reg;
   }
   function set reg(value)
   {
      this._reg = value;
   }
   function get clanName()
   {
      return this._clanName;
   }
   function set clanName(value)
   {
      this._clanName = value;
   }
   function get standingArray()
   {
      return this._standingArray;
   }
   function set standingArray(value)
   {
      this._standingArray = value;
   }
   function get memberList()
   {
      return this._memberList;
   }
   function set memberList(value)
   {
      this._memberList = value;
   }
}
