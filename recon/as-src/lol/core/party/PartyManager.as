class lol.core.party.PartyManager
{
   var DeclineInvite;
   var GroupList;
   var LeaderID;
   var XMC;
   var dispatchEvent;
   static var sInstance;
   static var singleCreation;
   static var PARTY_SEND_INVITE_PLAYER = 0;
   static var PARTY_SEND_KICK_PLAYER = 1;
   static var PARTY_SEND_SAY_YES = 2;
   static var PARTY_SEND_SAY_NO = 3;
   static var PARTY_SEND_CHANGE_LEADER = 4;
   static var PARTY_SEND_PARTY_LIST = 5;
   static var PARTY_RECEIVE_INVITE = 0;
   static var PARTY_RECEIVE_PLAYER_LEAVE = 1;
   static var PARTY_RECEIVE_PLAYER_KICKED = 2;
   static var PARTY_RECEIVE_LEADER_CHANGED = 3;
   static var PARTY_RECEIVE_JOIN = 4;
   static var PARTY_RECEIVE_RETURN_ONLINE = 5;
   static var PARTY_RECEIVE_DISCONNECTED = 6;
   static var PARTY_RECEIVE_EXIST = 7;
   static var PARTY_RECEIVE_REFUSE_INVITE = 8;
   static var PARTY_RECEIVE_DISBANDMENT = 9;
   function PartyManager()
   {
      if(lol.core.party.PartyManager.singleCreation)
      {
         this.init();
      }
   }
   function hasParty()
   {
      return this.GroupList.length > 1;
   }
   static function getInstance()
   {
      if(!lol.core.party.PartyManager.sInstance)
      {
         lol.core.party.PartyManager.singleCreation = true;
         lol.core.party.PartyManager.sInstance = new lol.core.party.PartyManager();
         lol.core.party.PartyManager.singleCreation = false;
      }
      return lol.core.party.PartyManager.sInstance;
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("p_op",this,this.PartyCommandReceived);
      this.XMC.addEventListener("p_m",this,this.PartyListReceived);
      this.GroupList = new Array();
      this.DeclineInvite = false;
   }
   function kill()
   {
      this.XMC.removeEventListener("p_op",this,this.PartyCommandReceived);
      this.XMC.removeEventListener("p_m",this,this.PartyListReceived);
   }
   function PartyCommandReceived(obj)
   {
      var _loc8_ = obj.param.op;
      var _loc2_ = 0;
      if(obj.param.mob_id != undefined)
      {
         _loc2_ = obj.param.mob_id;
      }
      var _loc10_ = lol.core.Master.getInstance().playerRegister.gamer;
      var _loc12_ = _loc10_.playerInfo.id;
      var _loc9_;
      var _loc11_;
      var _loc4_;
      var _loc6_;
      var _loc7_;
      var _loc5_;
      switch(_loc8_)
      {
         case lol.core.party.PartyManager.PARTY_RECEIVE_INVITE:
            if(this.DeclineInvite)
            {
               _loc9_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_SAY_NO,0);
               this.XMC.Send(_loc9_);
            }
            else
            {
               this.inviteInParty(_loc2_);
            }
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_PLAYER_LEAVE:
            this.leaveParty(_loc2_);
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_PLAYER_KICKED:
            this.leaveParty(_loc2_);
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_LEADER_CHANGED:
            this.setLeader(_loc2_);
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_JOIN:
            if(_loc2_)
            {
               if(this.GroupList.length == 0)
               {
                  if(this.GroupList[0] != 0)
                  {
                     this.GroupList.push(0);
                  }
               }
               this.GroupList.push(_loc2_);
            }
            this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.JOIN_TO_PARTY,null));
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_RETURN_ONLINE:
            this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.PLAYER_RETURN_ONLINE,obj.param.mob_id));
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_DISCONNECTED:
            this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.PLAYER_DISCONNECTED,obj.param.mob_id));
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_REFUSE_INVITE:
            _loc11_ = lol.core.SceneShifter.openNewWindow("alert","center");
            _loc4_ = lol.core.Master.getInstance();
            _loc6_ = "Игрок отклонил ваше приглашение в отряд";
            if(_loc4_)
            {
               _loc7_ = _loc4_.getPlayer(_loc2_);
               if(_loc7_)
               {
                  _loc5_ = _loc7_.playerInfo.name;
                  if(_loc5_)
                  {
                     _loc6_ = "Игрок " + _loc5_ + " отклонил ваше приглашение в отряд!";
                  }
               }
            }
            _loc11_.content.write(_loc6_);
            break;
         case lol.core.party.PartyManager.PARTY_RECEIVE_DISBANDMENT:
            this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.DISBAND_PARTY,null));
            this.GroupList.splice(0);
         default:
            return;
      }
   }
   function PartyListReceived(obj)
   {
      this.GroupList = obj.param.list;
      this.LeaderID = this.GroupList[0];
      this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.PARTY_LIST_REFRESH,null));
   }
   function PartyInviteForbidden(forbidden)
   {
      this.DeclineInvite = forbidden;
   }
   function leaveParty(playerID)
   {
      var _loc4_ = lol.core.Master.getInstance();
      var _loc5_ = _loc4_.playerRegister.gamer;
      var _loc2_;
      if(playerID == _loc5_.id)
      {
         this.GroupList.splice(0);
         this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.DISBAND_PARTY,null));
      }
      else
      {
         _loc2_ = 0;
         while(_loc2_ < this.GroupList.length)
         {
            if(this.GroupList[_loc2_] == playerID)
            {
               this.GroupList.splice(_loc2_,1);
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
         if(this.GroupList.length == 1)
         {
            this.GroupList.splice(0);
         }
         this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.LEAVE_PARTY,playerID));
      }
   }
   function setLeader(leaderID)
   {
      this.LeaderID = leaderID;
      var _loc2_;
      var _loc3_ = false;
      _loc2_ = 0;
      while(_loc2_ < this.GroupList.length)
      {
         if(this.GroupList[_loc2_] == leaderID)
         {
            this.GroupList.splice(_loc2_,1);
            _loc3_ = true;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc3_)
      {
         this.GroupList.unshift(leaderID);
      }
      this.dispatchEvent(new lol.core.party.PartyEvent(lol.core.party.PartyEvent.PARTY_LEADER_CHANGED,null));
   }
   function isLeader(userID)
   {
      return this.GroupList[0] == userID;
   }
   function weAreLeader()
   {
      return this.LeaderID == 0;
   }
   function inParty(id)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.GroupList.length)
      {
         if(this.GroupList[_loc2_] == id)
         {
            return true;
         }
         _loc2_ = _loc2_ + 1;
      }
      return false;
   }
   function inviteInParty(inviter)
   {
      var _loc3_ = lol.core.SceneShifter.openNewWindow("query");
      _loc3_.content.addEventListener("click",this,this.inviteAnswer);
      var _loc2_;
      var _loc4_ = lol.core.Master.getInstance();
      var _loc5_ = _loc4_.getPlayer(inviter);
      _loc2_ = _loc5_.playerInfo.name;
      if(!_loc2_)
      {
         _loc2_ = String(inviter);
      }
      _loc3_.content.label = "Персонаж " + _loc2_ + " приглашает вас отряд";
      this.setLeader(inviter);
   }
   function inviteAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.inviteAnswer);
      lol.core.SceneShifter.closeWindow("query");
      this.sendInviteAnswer(obj.success);
   }
   function sendInviteAnswer(sayYes)
   {
      var _loc2_ = !sayYes ? lol.core.party.PartyManager.PARTY_SEND_SAY_NO : lol.core.party.PartyManager.PARTY_SEND_SAY_YES;
      var _loc3_ = new lol.server.mess.CSM_P_OP(_loc2_,0);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.errorReport,_loc2_);
      }
   }
   function errorReport(obj)
   {
      var _loc4_ = obj.param.data;
      var _loc2_;
      if(obj.param.res != 0)
      {
         trace("PartyManager -> errorReport -> ERROR CODE = " + obj.param.res);
      }
      else
      {
         _loc2_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_PARTY_LIST,0);
         if(!this.XMC.Send(_loc2_))
         {
         }
      }
   }
}
