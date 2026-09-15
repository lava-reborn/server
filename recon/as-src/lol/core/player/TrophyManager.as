class lol.core.player.TrophyManager extends lol.core.player.StuffManager
{
   var XMC;
   var createItem;
   var dispatchEvent;
   var master;
   var trophy_arr;
   static var SESSION_TYPE = 6;
   static var UPD_CLOSE = 0;
   static var UPD_SET_PUBLIC = 1;
   static var UPD_PUBLIC_COUNT = 2;
   static var UPD_BY_PUBLIC = 3;
   static var UPD_DELETE_TROPHY = 4;
   static var CREATE_SESSION_SUCCESS = "CREATE_SESSION_SUCCESS";
   static var CREATE_SESSION_ERROR = "CREATE_SESSION_ERROR";
   static var SET_PUBLIC_SUCCESS = "SET_PUBLIC_SUCCESS";
   static var SET_PUBLIC_ERROR = "SET_PUBLIC_ERROR";
   static var PUBLIC_SLOT_NUM = "PUBLIC_SLOT_NUM";
   static var TROPHY_LIST = "TROPHY_LIST";
   static var ADD_SLOT = "ADD_SLOT";
   static var DELETE_TROPHY = "DELETE_TROPHY";
   var session_bool = false;
   function TrophyManager()
   {
      super();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_upd",this,this.ss_upd);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      this.master = lol.core.Master.getInstance();
   }
   function ss_upd(obj)
   {
      var _loc2_ = obj.param.s_status;
      var _loc3_;
      if(_loc2_ == lol.core.player.TrophyManager.UPD_CLOSE)
      {
         this.dispatchEvent({type:"close"});
      }
      else
      {
         _loc3_ = Number("0" + obj.param.obj);
         this.dispatchEvent({type:lol.core.player.TrophyManager.PUBLIC_SLOT_NUM,num:_loc3_});
      }
   }
   function createSession()
   {
      var _loc2_ = new lol.server.mess.CSM_SSCreate(lol.core.player.TrophyManager.SESSION_TYPE,lol.core.player.Gamer.ID);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.createSessionAck);
      }
   }
   function createSessionAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         this.session_bool = true;
         this.requestTrophy();
         this.master.gamer.equipment.requestPublicTrophy();
         this.dispatchEvent({type:lol.core.player.TrophyManager.CREATE_SESSION_SUCCESS});
      }
      else
      {
         this.session_bool = false;
         this.dispatchEvent({type:lol.core.player.TrophyManager.CREATE_SESSION_ERROR});
      }
   }
   function closeSession()
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.TrophyManager.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      this.XMC.Send(_loc2_);
   }
   function setPublicTrophy(item, slotNum)
   {
      var _loc2_ = item != 0 ? item.oID : 0;
      var _loc4_;
      if((_loc2_ || _loc2_ == 0) && (slotNum || slotNum == 0))
      {
         _loc4_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.TrophyManager.UPD_SET_PUBLIC,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)),slotNum);
         if(this.XMC.Send(_loc4_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.setPublicTrophyAck);
         }
      }
   }
   function setPublicTrophyAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatchEvent({type:lol.core.player.TrophyManager.SET_PUBLIC_SUCCESS});
         this.master.gamer.equipment.requestPublicTrophy();
      }
      else
      {
         this.dispatchEvent({type:lol.core.player.TrophyManager.SET_PUBLIC_ERROR});
      }
   }
   function requestTrophy()
   {
      var _loc2_ = 16;
      var _loc3_ = new lol.server.mess.CSM_SSGet(_loc2_,lol.core.player.Gamer.ID);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("ss_ack",this,this.requestTrophyAck);
      }
   }
   function requestTrophyAck(obj)
   {
      var _loc7_ = obj.param;
      var _loc5_ = obj.param.o_list;
      this.trophy_arr = new Array();
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < _loc5_.length)
      {
         _loc3_ = _loc5_[_loc2_];
         _loc4_ = this.createItem(_loc3_);
         this.trophy_arr.push(_loc4_);
         _loc2_ = _loc2_ + 1;
      }
      this.dispatchEvent({type:lol.core.player.TrophyManager.TROPHY_LIST});
   }
   function addSlot()
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.TrophyManager.UPD_BY_PUBLIC);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.addSlotAck);
      }
   }
   function addSlotAck(obj)
   {
      var _loc4_ = obj.param;
      this.dispatchEvent({type:lol.core.player.TrophyManager.ADD_SLOT,success:obj.param.res == 0});
      if(obj.param.res == 0)
      {
         this.master.gamer.equipment.requestPublicTrophy();
      }
   }
   function deleteTrophy(item)
   {
      var _loc2_ = item.oID;
      var _loc3_;
      if(_loc2_)
      {
         _loc3_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.TrophyManager.UPD_DELETE_TROPHY,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.deleteTrophyAck,item);
         }
      }
   }
   function deleteTrophyAck(obj)
   {
      var _loc5_ = obj.param;
      if(obj.param.res == 0)
      {
         for(var _loc3_ in this.trophy_arr)
         {
            if(this.trophy_arr[_loc3_] == obj.data)
            {
               this.trophy_arr.splice(Number(_loc3_),1);
               break;
            }
         }
         this.master.gamer.equipment.requestPublicTrophy();
      }
      this.dispatchEvent({type:lol.core.player.TrophyManager.DELETE_TROPHY,success:obj.param.res == 0});
   }
}
