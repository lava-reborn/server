class lol.core.clans.ClanInspector
{
   var XMC;
   var clanArray;
   var clanCreationCost;
   var dispatchEvent;
   var downStandingCost;
   var inClan;
   var infoReceived;
   var master;
   var upStandingCost;
   static var sInstance;
   static var singleCreation;
   function ClanInspector()
   {
      if(lol.core.clans.ClanInspector.singleCreation)
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.core.clans.ClanInspector.sInstance)
      {
         lol.core.clans.ClanInspector.singleCreation = true;
         lol.core.clans.ClanInspector.sInstance = new lol.core.clans.ClanInspector();
         lol.core.clans.ClanInspector.singleCreation = false;
      }
      return lol.core.clans.ClanInspector.sInstance;
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.master = lol.core.Master.getInstance();
      this.clanArray = new Array();
      this.XMC.addEventListener("fellow",this);
      this.XMC.addEventListener("invite",this);
      this.XMC.addEventListener("gg_struct",this);
      this.XMC.addEventListener("gg_list",this);
      this.XMC.addEventListener("gg_code",this);
      this.XMC.addEventListener("userInfo",this,this.userInfo);
      this.XMC.addEventListener("userInfo_Commoner",this,this.userInfo);
      this.XMC.addEventListener("userInfo_Medic",this,this.userInfo);
      this.XMC.addEventListener("userInfo_SpecTrainer",this,this.userInfo);
      this.XMC.addEventListener("userInfo_Trader",this,this.userInfo);
      this.XMC.addEventListener("userInfo_Upgrader",this,this.userInfo);
      this.XMC.addEventListener("userInfo_Player",this,this.userInfo);
      this.XMC.addEventListener("onClose",this);
      this.master.addEventListener("changeState",this,this.firstRequest);
   }
   function kill()
   {
      this.XMC.removeEventListener("fellow",this);
      this.XMC.removeEventListener("invite",this);
      this.XMC.removeEventListener("gg_struct",this);
      this.XMC.removeEventListener("gg_list",this);
      this.XMC.removeEventListener("gg_code",this);
      this.XMC.removeEventListener("userInfo",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_Commoner",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_Medic",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_SpecTrainer",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_Trader",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_Upgrader",this,this.userInfo);
      this.XMC.removeEventListener("userInfo_Player",this,this.userInfo);
      this.XMC.removeEventListener("onClose",this);
      this.master.removeEventListener("changeState",this,this.firstRequest);
   }
   function createClan(name, desc)
   {
      var _loc2_ = new lol.server.mess.CSM_C_Head(new lol.data.GDString(name),new lol.data.GDString(desc));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.createClanCmdAck);
      }
   }
   function getClanMemberList()
   {
      var _loc2_ = this.master.gamer.clanMemberInfo.clanReg;
      if(_loc2_ != 0 && _loc2_ != 16777215)
      {
         return this.clanArray[_loc2_].memberList;
      }
      return new Array();
   }
   function inviteToClan(charName, rights, post)
   {
      var _loc2_ = rights;
      if(this.master.gamer.clanMemberInfo.rights.allowAcceptNewMiddleMembers == true)
      {
         _loc2_.baseRights = true;
      }
      else
      {
         _loc2_.baseRights = false;
      }
      var _loc3_ = new lol.server.mess.CSM_C_Admit(new lol.data.GDString(charName),_loc2_.rightsCode,new lol.data.GDString(post));
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.admitCmdAck);
      }
   }
   function inviteAnswer(agree)
   {
      var _loc3_ = !agree ? 1 : 2;
      var _loc2_ = new lol.server.mess.CSM_C_Apply(0,_loc3_);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.inviteAnswerCmdAck);
      }
   }
   function leaveClan()
   {
      var _loc2_ = new lol.server.mess.CSM_C_Apply(0,1);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.leaveClanCmdAck);
      }
   }
   function changeClanInvitationState()
   {
      var _loc2_ = new lol.server.mess.CSM_C_Apply(0,0);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.invitationClanStateCmdAck);
      }
   }
   function getClanCreationCost()
   {
      var _loc2_;
      if(this.clanCreationCost == undefined)
      {
         _loc2_ = new lol.server.mess.CSM_C_GG_Info(6);
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.getClanCreationCostCmdAck);
         }
      }
      return this.clanCreationCost;
   }
   function getStandingCost()
   {
      var _loc2_ = new lol.server.mess.CSM_C_GG_Info(6);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getStandingCostCmdAck);
      }
   }
   function kickClanMember(clanMemberInfo)
   {
      var _loc2_ = new lol.server.mess.CSM_C_Apply(clanMemberInfo.char,1);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.kickClanMemberCmdAck);
      }
   }
   function changeRights(clanMemberInfo, setRights, post)
   {
      var _loc2_ = setRights;
      if(this.master.gamer.clanMemberInfo.rights.allowAcceptNewMiddleMembers == true)
      {
         _loc2_.baseRights = true;
      }
      else
      {
         _loc2_.baseRights = false;
      }
      var _loc3_ = new lol.server.mess.CSM_C_Admit_Char(clanMemberInfo.char,_loc2_.rightsCode,new lol.data.GDString(post));
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.changeRightsCmdAck);
      }
   }
   function getClanAccauntGoldAmmount()
   {
      var _loc2_ = new lol.server.mess.CSM_C_GG_Info(4);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getClanAccountGoldAmmountCmdAck);
      }
   }
   function getStanding(clanId)
   {
      var _loc3_;
      if(clanId != undefined && !isNaN(clanId) && clanId != 0)
      {
         _loc3_ = new lol.server.mess.CSM_C_Apply(clanId,7);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.getStandingCmdAck);
         }
      }
   }
   function getStandingCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_STANDING_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_STANDING_SUCCES));
         default:
            return;
      }
   }
   function getClanAccauntAfroAmmount()
   {
      var _loc2_ = new lol.server.mess.CSM_C_GG_Info(3);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getClanAccountAfroAmmountCmdAck);
      }
   }
   function addMoneyToClanAccount(moneyType, moneyAmmount)
   {
      var _loc2_;
      switch(moneyType)
      {
         case "GOLD":
            _loc2_ = new lol.server.mess.CSM_C_Apply(moneyAmmount,4);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.addMoneyToClanAccountCmdAck);
            }
            break;
         case "AFRO":
            _loc2_ = new lol.server.mess.CSM_C_Apply(moneyAmmount,3);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.addMoneyToClanAccountCmdAck);
            }
         default:
            return;
      }
   }
   function withdrawMoneyFromClanAccount(moneyType, moneyAmmount)
   {
      var _loc2_;
      switch(moneyType)
      {
         case "GOLD":
            _loc2_ = new lol.server.mess.CSM_C_Apply(- moneyAmmount,4);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.withdrawMoneyFromClanAccountCmdAck);
            }
            break;
         case "AFRO":
            _loc2_ = new lol.server.mess.CSM_C_Apply(- moneyAmmount,3);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.withdrawMoneyFromClanAccountCmdAck);
            }
         default:
            return;
      }
   }
   function setStanding(type, clanID)
   {
      var _loc2_;
      switch(type)
      {
         case "up":
            _loc2_ = new lol.server.mess.CSM_C_Apply(clanID,5);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.setStandingCmdAck);
            }
            break;
         case "down":
            _loc2_ = new lol.server.mess.CSM_C_Apply(clanID,6);
            if(this.XMC.Send(_loc2_))
            {
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.setStandingCmdAck);
            }
         default:
            return;
      }
   }
   function setStandingCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.SET_STANDING_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.SET_STANDING_SUCCES));
            break;
         case 21:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.SET_STANDING_NO_MONEY));
         default:
            return;
      }
   }
   function gg_code(resObj)
   {
      if(resObj.param.res == 20)
      {
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CHANGE_RIGHTS_FAILED_NOT_ENOUGH_RIGHTS));
      }
   }
   function changeRightsCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CHANGE_RIGHTS_ERROR_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CHANGE_RIGHTS_SUCCES));
            break;
         case 23:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CHANGE_RIGHTS_STRING_TOO_LONG));
         default:
            return;
      }
   }
   function getStandingCostCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.STANDING_COST_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.STANDING_COST_SUCCES));
         default:
            return;
      }
   }
   function getClanCreationCostCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_COST_ERROR_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_COST_SUCCES));
         default:
            return;
      }
   }
   function getClanAccountGoldAmmountCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_CLAN_ACCOUNT_GOLD_AMMOUNT_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_CLAN_ACCOUNT_GOLD_AMMOUNT_SUCCES));
         default:
            return;
      }
   }
   function getClanAccountAfroAmmountCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_CLAN_ACCOUNT_AFRO_AMMOUNT_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.GET_CLAN_ACCOUNT_AFRO_AMMOUNT_SUCCES));
         default:
            return;
      }
   }
   function addMoneyToClanAccountCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.ADD_MONEY_TO_CLAN_AMMOUNT_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.ADD_MONEY_TO_CLAN_AMMOUNT_SUCCES));
            break;
         case 21:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.ADD_MONEY_TO_CLAN_AMMOUNT_CANT_AFFORD));
         default:
            return;
      }
   }
   function withdrawMoneyFromClanAccountCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.WITHDRAW_MONEY_FROM_CLAN_AMMOUNT_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.WITHDRAW_MONEY_FROM_CLAN_AMMOUNT_SUCCES));
            break;
         case 21:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.WITHDRAW_MONEY_FROM_CLAN_AMMOUNT_CANT_AFFORD));
         default:
            return;
      }
   }
   function kickClanMemberCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.KICK_MEMBER_ERROR_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.KICK_MEMBER_SUCCES));
            this.getClanMemberListFromServer();
         default:
            return;
      }
   }
   function invitationClanStateCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_INVITATION_STATE_ERROR_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_INVITATION_STATE_SUCCES));
         default:
            return;
      }
   }
   function createClanCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 5:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_INVALID_NAME));
            break;
         case 6:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_USED_NAME));
            break;
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_SUCCES));
            break;
         case 21:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_NO_MONEY));
         default:
            return;
      }
   }
   function gg_struct(resObj)
   {
      var _loc3_ = new lol.core.clans.GgStructCommad(resObj.param);
      var _loc2_ = this.getMemberByID(_loc3_.id);
      var _loc4_;
      var _loc5_;
      switch(_loc3_.act)
      {
         case 0:
            _loc2_.date = _loc3_.date;
            _loc2_.online = 1;
            _loc2_.rights.rightsCode = _loc3_.perm;
            break;
         case 1:
            if(!_loc2_)
            {
               _loc2_ = new lol.core.clans.ClanMemberInfo();
               this.master.gamer.clanMemberInfo.clanInfo.memberList.push(_loc2_);
            }
            _loc2_.date = _loc3_.date;
            _loc2_.char = _loc3_.id;
            _loc2_.memberPost = _loc3_.post;
            _loc2_.rights.rightsCode = _loc3_.perm;
            _loc2_.name = _loc3_.name;
            _loc2_.clanInfo = this.master.gamer.clanMemberInfo.clanInfo;
            _loc4_ = this.master.getPlayerByName(_loc2_.name);
            if(_loc4_)
            {
               _loc2_.online = _loc4_.id;
               _loc4_.clanMemberInfo = _loc2_;
               _loc4_.clanMemberInfo.clanReg = this.master.gamer.clanMemberInfo.clanReg;
            }
            else
            {
               _loc2_.online = 1;
            }
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.NEW_CLAN_MEMBER_ADDED,null));
            break;
         case 2:
            _loc4_ = this.master.getPlayerByName(_loc2_.name);
            _loc4_.clanMemberInfo.clanReg = 0;
            _loc5_ = this.getMemberIndexByID(_loc3_.id);
            this.master.gamer.clanMemberInfo.clanInfo.memberList.splice(_loc5_,1);
            break;
         case 3:
            _loc2_.memberPost = _loc3_.post;
            _loc2_.rights.rightsCode = _loc3_.perm;
            break;
         case 4:
            _loc2_.online = 0;
      }
      this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,null));
   }
   function requestAllPlayer()
   {
      var _loc3_ = this.master.currentLocation.playerList;
      var _loc2_;
      for(var _loc4_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc4_];
         if(!(_loc2_ instanceof lol.core.player.Player))
         {
            _loc2_.requestInfo();
         }
      }
   }
   function gg_list(resObj)
   {
      var _loc2_ = new lol.core.clans.GgListCommand(resObj.param);
      var _loc5_;
      if(_loc2_.res == 9)
      {
         _loc5_ = this.getClanStandingInfo(_loc2_.data[0]);
         if(_loc5_ == undefined)
         {
            this.createNewClanStanding(_loc2_.data[0],_loc2_.names[0],0,_loc2_.stats[0]);
         }
         else
         {
            _loc5_.theirStat = _loc2_.stats[0];
         }
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.THEY_SET_STANDING,_loc5_));
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE));
         return undefined;
      }
      if(_loc2_.res == 8)
      {
         _loc5_ = this.getClanStandingInfo(_loc2_.data[0]);
         if(_loc5_ == undefined)
         {
            this.createNewClanStanding(_loc2_.data[0],_loc2_.names[0],_loc2_.stats[0]);
         }
         else
         {
            _loc5_.stat = _loc2_.stats[0];
         }
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.WE_SET_STANDING,_loc5_));
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE));
         return undefined;
      }
      if(_loc2_.res == 6)
      {
         this.clanCreationCost = _loc2_.data[0];
         this.downStandingCost = _loc2_.data[1];
         this.upStandingCost = _loc2_.data[2];
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_CREATION_COST,_loc2_.data[0]));
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.STANDING_COST));
         return undefined;
      }
      if(_loc2_.res == 5)
      {
         _loc5_ = this.getClanStandingInfo(_loc2_.data[0]);
         _loc5_.theirStat = _loc2_.stats[0];
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE));
         return undefined;
      }
      if(_loc2_.res == 4)
      {
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ACCOUNT_GOLD_AMMOUNT,_loc2_.data[0]));
         return undefined;
      }
      if(_loc2_.res == 3)
      {
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ACCOUNT_AFRO_AMMOUNT,_loc2_.data[0]));
         return undefined;
      }
      var _loc6_;
      var _loc8_;
      var _loc9_;
      var _loc3_;
      var _loc7_;
      if(_loc2_.res == 0)
      {
         _loc6_ = this.master.gamer.clanMemberInfo.clanInfo;
         _loc8_ = _loc6_.reg;
         this.clanArray[_loc8_].standingArray = new Array();
         _loc9_ = _loc2_.data.length;
         _loc3_ = 0;
         _loc7_ = 0;
         while(_loc3_ < _loc9_)
         {
            if(_loc2_.data[_loc3_] != 0 && _loc2_.names[_loc3_] != "")
            {
               _loc5_ = new lol.core.clans.ClanStandingInfo();
               _loc5_.stat = _loc2_.stats[_loc3_];
               _loc5_.name = _loc2_.names[_loc3_];
               _loc5_.data = _loc2_.data[_loc3_];
               this.clanArray[_loc8_].standingArray[_loc2_.data[_loc7_]] = _loc5_;
               _loc7_ = _loc7_ + 1;
            }
            _loc3_ = _loc3_ + 1;
         }
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE));
         return undefined;
      }
      _loc6_ = this.master.gamer.clanMemberInfo.clanInfo;
      _loc6_.memberList = new Array();
      _loc3_ = 0;
      var _loc4_;
      while(_loc3_ < _loc2_.data.length)
      {
         _loc4_ = new lol.core.clans.ClanMemberInfo();
         _loc4_.date = _loc2_.dates[_loc3_];
         _loc4_.online = _loc2_.stats[_loc3_];
         _loc4_.char = _loc2_.data[_loc3_];
         _loc4_.memberPost = _loc2_.posts[_loc3_];
         _loc4_.rights.rightsCode = _loc2_.perms[_loc3_];
         _loc4_.name = _loc2_.names[_loc3_];
         _loc4_.clanInfo = _loc6_;
         _loc6_.memberList[_loc3_] = _loc4_;
         _loc3_ = _loc3_ + 1;
      }
      this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE));
   }
   function createNewClanStanding(clanID, name, stat, theirStat)
   {
      if(!this.clanArray[this.master.gamer.clanMemberInfo.clanInfo.reg].standingArray)
      {
         this.clanArray[this.master.gamer.clanMemberInfo.clanInfo.reg].standingArray = new Array();
      }
      var _loc3_ = this.master.gamer.clanMemberInfo.clanInfo;
      this.clanArray[_loc3_.reg].standingArray[clanID] = new lol.core.clans.ClanStandingInfo();
      var _loc2_ = this.clanArray[_loc3_.reg].standingArray[clanID];
      _loc2_.stat = stat;
      _loc2_.name = name;
      _loc2_.data = theirStat;
   }
   function fellow(obj)
   {
      var _loc2_ = new lol.core.clans.FellowCommand(obj.param);
      var _loc3_;
      var _loc5_;
      if(_loc2_.reg == 0 && _loc2_.id == 0 && this.master.gamer.clanMemberInfo.clanInfo.reg != 0)
      {
         _loc5_ = this.master.gamer.clanMemberInfo.clanInfo.reg;
         this.master.gamer.clanMemberInfo.rights.rightsCode = null;
         this.master.gamer.clanMemberInfo.clanReg = _loc2_.reg;
         this.infoReceived = false;
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.KICKED_FROM_CLAN));
         this.requestAllPlayer();
         return undefined;
      }
      if(_loc2_.id == 0 && (_loc2_.reg == 0 || _loc2_.reg == 16777215))
      {
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.FREE_USER_AGREE_TO_RECEIVE_INVITES));
         this.master.gamer.clanMemberInfo.clanReg = _loc2_.reg;
         return undefined;
      }
      var _loc4_;
      if(_loc2_.id == 0 && _loc2_.reg != 0)
      {
         if(this.clanArray[_loc2_.reg] == undefined)
         {
            this.clanArray[_loc2_.reg] = new lol.core.clans.ClanInfo(_loc2_.reg,_loc2_.soc);
         }
         this.master.gamer.clanMemberInfo = new lol.core.clans.ClanMemberInfo();
         this.master.gamer.clanMemberInfo.initByFellowMessage(_loc2_);
         this.master.gamer.clanMemberInfo.clanInfo = this.clanArray[_loc2_.reg];
         _loc4_ = this.master.gamer.clanMemberInfo;
         _loc4_.memberPost = _loc2_.post;
         _loc4_.rights.rightsCode = _loc2_.perm;
         this.requestAllPlayer();
         this.inClan = true;
         this.firstRequest(new Object());
         this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE));
      }
      else
      {
         _loc3_ = this.master.getPlayer(_loc2_.id);
         if(_loc3_.playerInfo.name != "Солдат СА")
         {
            _loc3_.clanMemberInfo = new lol.core.clans.ClanMemberInfo();
            if(this.clanArray[_loc2_.reg] == undefined)
            {
               this.clanArray[_loc2_.reg] = new lol.core.clans.ClanInfo(_loc2_.reg,_loc2_.soc);
            }
            _loc3_.clanMemberInfo.initByFellowMessage(_loc2_);
            _loc3_.clanMemberInfo.clanInfo = this.clanArray[_loc2_.reg];
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.OTHER_CLAN_MEMBER_ARRIVED,_loc3_));
         }
      }
   }
   function userInfo(obj)
   {
      var _loc9_ = obj.param.ally;
      var _loc3_ = obj.param.clan;
      var _loc7_ = obj.param.id;
      var _loc5_ = this.master.getPlayer(_loc7_);
      var _loc4_;
      var _loc2_;
      if(!(_loc5_ instanceof lol.core.player.Player) && _loc7_ != lol.core.player.Gamer.ID)
      {
         if(_loc3_ != undefined)
         {
            _loc5_.clanMemberInfo = new lol.core.clans.ClanMemberInfo();
            if(this.clanArray[_loc3_] == undefined)
            {
               _loc2_ = this.clanArray[this.master.gamer.clanMemberInfo.clanInfo.reg].standingArray;
               for(var _loc6_ in _loc2_)
               {
                  if(Number(_loc6_) == _loc3_)
                  {
                     _loc4_ = _loc2_[_loc6_].name;
                     break;
                  }
               }
               if(_loc4_)
               {
                  this.clanArray[_loc3_] = new lol.core.clans.ClanInfo(_loc3_,_loc4_);
               }
            }
            _loc5_.clanMemberInfo.clanReg = _loc3_;
            _loc5_.clanMemberInfo.clanInfo = this.clanArray[_loc3_];
         }
         else
         {
            _loc5_.clanMemberInfo.clanReg = 0;
         }
      }
      this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.OTHER_CLAN_MEMBER_ARRIVED,_loc5_));
   }
   function getClanMemberListFromServer()
   {
      var _loc2_ = new lol.server.mess.CSM_C_GG_Info(1);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getClanMemberListCmdAck);
      }
   }
   function getClanMemberListCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LIST_ANSWER_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LIST_ANSWER_SUCCES));
            break;
         case 9:
            this.doLater_getClanMemberList();
         default:
            return;
      }
   }
   function doLater_getClanMemberList()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.getClanMemberListFromServer,5000);
   }
   function getClanStandingFromServer()
   {
      var _loc2_ = new lol.server.mess.CSM_C_GG_Info(5);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getClanStandingCmdAck);
      }
   }
   function getClanStandingCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_ANSWER_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_STANDING_ANSWER_SUCCES));
            break;
         case 9:
            this.doLater_getClanStanding();
         default:
            return;
      }
   }
   function doLater_getClanStanding()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.getClanStandingFromServer,5000);
   }
   function firstRequest(obj)
   {
      if(!this.infoReceived && this.inClan)
      {
         if(this.master.currentState == lol.core.Master.LOCAL_STATE || this.master.currentState == lol.core.Master.GLOBAL_STATE)
         {
            this.getClanMemberListFromServer();
            if(this.master.gamer.clanMemberInfo.rights.allowChatAndViewStandings)
            {
               this.getClanStandingFromServer();
            }
            this.infoReceived = true;
         }
      }
   }
   function onClose(obj)
   {
      this.infoReceived = false;
      this.kill();
   }
   function invite(obj)
   {
      this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_INVITE_RECEIVED,new lol.core.clans.InviteObject(obj.param)));
   }
   function inviteAnswerCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES));
         default:
            return;
      }
   }
   function admitCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 22:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_FOUND_ERROR));
            break;
         case 28:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_PLAYER_IN_OTHER_CLAN_ERROR));
            break;
         case 30:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_ONLINE_ERROR));
            break;
         case 23:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_STRING_TO_LONG_ERROR));
            break;
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_BAN_ERROR));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_ADMIT_SUCCES));
         default:
            return;
      }
   }
   function leaveClanCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 2:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LEAVE_BAN));
            break;
         case 0:
            this.dispatchEvent(new lol.core.clans.ClanEvent(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES));
         default:
            return;
      }
   }
   function getClanStandingInfo(clanID)
   {
      var _loc3_ = this.master.gamer.clanMemberInfo.clanInfo.reg;
      var _loc2_ = this.clanArray[_loc3_].standingArray[clanID];
      return _loc2_;
   }
   function getMemberByID(id)
   {
      var _loc4_ = this.master.gamer.clanMemberInfo.clanInfo;
      var _loc3_;
      var _loc5_ = false;
      var _loc6_ = _loc4_.memberList;
      var _loc2_ = 0;
      while(_loc2_ < _loc6_.length)
      {
         _loc3_ = _loc4_.memberList[_loc2_];
         if(id == _loc3_.char)
         {
            _loc5_ = true;
            return _loc3_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getMemberByName(name)
   {
      var _loc4_ = this.master.gamer.clanMemberInfo.clanInfo;
      var _loc3_;
      var _loc5_ = _loc4_.memberList;
      var _loc2_ = 0;
      while(_loc2_ < _loc5_.length)
      {
         _loc3_ = _loc4_.memberList[_loc2_];
         if(name == _loc3_.name)
         {
            return _loc3_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getMemberIndexByID(id)
   {
      var _loc3_ = this.master.gamer.clanMemberInfo.clanInfo;
      var _loc4_;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.memberList.length)
      {
         _loc4_ = _loc3_.memberList[_loc2_];
         if(id == _loc4_.char)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return null;
   }
}
