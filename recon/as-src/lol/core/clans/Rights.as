class lol.core.clans.Rights
{
   var _rightsCode;
   var _baseRights = true;
   var _allowChatAndViewStandings = false;
   var _allowAddItemsToClanStorage = false;
   var _allowGetItemsFromClanStorage = false;
   var _allowAcceptNewBaseMembers = false;
   var _allowFireBaseMembers = false;
   var _allowAcceptNewMiddleMembers = false;
   var _allowGetAfroFromClanBank = false;
   var _allowGetGoldFromClanBank = false;
   var _allowChangeStandings = false;
   var _allowAllOtherRights = false;
   var _clanLeader = false;
   function Rights()
   {
   }
   function parseRightsCode(pRightsCode)
   {
      this._baseRights = true;
      this._allowChatAndViewStandings = Boolean(pRightsCode & 2);
      this._allowAddItemsToClanStorage = Boolean(pRightsCode & 4);
      this._allowGetItemsFromClanStorage = Boolean(pRightsCode & 0x20);
      this._allowAcceptNewBaseMembers = Boolean(pRightsCode & 0x40);
      this._allowFireBaseMembers = Boolean(pRightsCode & 0x0100);
      this._allowAcceptNewMiddleMembers = Boolean(pRightsCode & 0x0200);
      this._allowGetAfroFromClanBank = Boolean(pRightsCode & 0x0400);
      this._allowGetGoldFromClanBank = Boolean(pRightsCode & 0x0800);
      this._allowChangeStandings = Boolean(pRightsCode & 0x2000);
      this._allowAllOtherRights = Boolean(pRightsCode & 0x8000);
      this._clanLeader = Boolean(pRightsCode & 0xFFFF);
   }
   function get rightsCode()
   {
      return this._rightsCode;
   }
   function set rightsCode(value)
   {
      this._rightsCode = value;
      this.parseRightsCode(value);
   }
   function updateRightsCode()
   {
      this._rightsCode = 0;
      !this._baseRights ? (this._rightsCode += 0) : (this._rightsCode += 1);
      if(!this._clanLeader)
      {
         !this._allowChatAndViewStandings ? (this._rightsCode += 0) : (this._rightsCode += 2);
         !this._allowAddItemsToClanStorage ? (this._rightsCode += 0) : (this._rightsCode += 4);
         !this._allowGetItemsFromClanStorage ? (this._rightsCode += 0) : (this._rightsCode += 32);
         !this._allowAcceptNewBaseMembers ? (this._rightsCode += 0) : (this._rightsCode += 64);
         !this._allowFireBaseMembers ? (this._rightsCode += 0) : (this._rightsCode += 256);
         !this._allowAcceptNewMiddleMembers ? (this._rightsCode += 0) : (this._rightsCode += 512);
         !this._allowGetAfroFromClanBank ? (this._rightsCode += 0) : (this._rightsCode += 1024);
         !this._allowGetGoldFromClanBank ? (this._rightsCode += 0) : (this._rightsCode += 2048);
         !this._allowChangeStandings ? (this._rightsCode += 0) : (this._rightsCode += 8192);
         !this._allowAllOtherRights ? (this._rightsCode += 0) : (this._rightsCode += 32768);
      }
      else
      {
         this._rightsCode = 65535;
      }
   }
   function get baseRights()
   {
      return this._baseRights;
   }
   function set baseRights(value)
   {
      this._baseRights = value;
      this.updateRightsCode();
   }
   function get allowChatAndViewStandings()
   {
      return this._allowChatAndViewStandings;
   }
   function set allowChatAndViewStandings(value)
   {
      this._allowChatAndViewStandings = value;
      this.updateRightsCode();
   }
   function get allowAddItemsToClanStorage()
   {
      return this._allowAddItemsToClanStorage;
   }
   function set allowAddItemsToClanStorage(value)
   {
      this._allowAddItemsToClanStorage = value;
      this.updateRightsCode();
   }
   function get allowGetItemsFromClanStorage()
   {
      return this._allowGetItemsFromClanStorage;
   }
   function set allowGetItemsFromClanStorage(value)
   {
      this._allowGetItemsFromClanStorage = value;
      this.updateRightsCode();
   }
   function get allowAcceptNewBaseMembers()
   {
      return this._allowAcceptNewBaseMembers;
   }
   function set allowAcceptNewBaseMembers(value)
   {
      this._allowAcceptNewBaseMembers = value;
      this.updateRightsCode();
   }
   function get allowFireBaseMembers()
   {
      return this._allowFireBaseMembers;
   }
   function set allowFireBaseMembers(value)
   {
      this._allowFireBaseMembers = value;
      this.updateRightsCode();
   }
   function get allowAcceptNewMiddleMembers()
   {
      return this._allowAcceptNewMiddleMembers;
   }
   function set allowAcceptNewMiddleMembers(value)
   {
      this._allowAcceptNewMiddleMembers = value;
      this.updateRightsCode();
   }
   function get allowGetAfroFromClanBank()
   {
      return this._allowGetAfroFromClanBank;
   }
   function set allowGetAfroFromClanBank(value)
   {
      this._allowGetAfroFromClanBank = value;
      this.updateRightsCode();
   }
   function get allowGetGoldFromClanBank()
   {
      return this._allowGetGoldFromClanBank;
   }
   function set allowGetGoldFromClanBank(value)
   {
      this._allowGetGoldFromClanBank = value;
      this.updateRightsCode();
   }
   function get allowChangeStandings()
   {
      return this._allowChangeStandings;
   }
   function set allowChangeStandings(value)
   {
      this._allowChangeStandings = value;
      this.updateRightsCode();
   }
   function get allowAllOtherRights()
   {
      return this._allowAllOtherRights;
   }
   function set allowAllOtherRights(value)
   {
      this._allowAllOtherRights = value;
      this.updateRightsCode();
   }
   function get clanLeader()
   {
      return this._clanLeader;
   }
   function set clanLeader(value)
   {
      this._clanLeader = value;
      this.updateRightsCode();
   }
}
