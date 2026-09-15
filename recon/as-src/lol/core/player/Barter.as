class lol.core.player.Barter extends lol.core.player.StuffManager
{
   var XMC;
   var __iReady;
   var __vavReady;
   var alertPan;
   var awaitingAnswerInt;
   var bag;
   var dialogPan;
   var dispatchEvent;
   var master;
   var moneyTransfer;
   var myBarterList;
   var proposed;
   var transferStack;
   var visavisBarterList;
   var visavisID;
   static var UPD_CLOSE = 0;
   static var UPD_AGREE = 1;
   static var UPD_DENY = 2;
   static var UPD_TO_BUFFER = 3;
   static var UPD_TO_BAG = 4;
   static var UPD_APPLY = 5;
   static var UPD_BREAK = 6;
   static var UPD_ADD_AFRO = 7;
   static var UPD_ADD_GOLD = 8;
   function Barter()
   {
      super();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_upd",this);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      this.bag = _loc3_.equipment.bag;
      this.myBarterList = new lol.core.player.Bag("myBarterList");
      this.visavisBarterList = new lol.core.player.Bag("visavisBarterList");
      this.master = lol.core.Master.getInstance();
   }
   function createSession(pos)
   {
      this.proposed = false;
      lol.core.SceneShifter.closeWindow("query");
      lol.core.SceneShifter.closeWindow("alert");
      var _loc2_ = lol.core.SceneShifter.openNewWindow("barter");
      this.requestSession();
   }
   function requestSession()
   {
      var _loc2_ = this.bag.maskIndex;
      this.getStuff(_loc2_);
   }
   function ss_ack(obj)
   {
      var _loc2_ = obj.param.o_list;
      if(_loc2_.length > 0)
      {
         this.parseBag(_loc2_);
      }
   }
   function parseBag(arr)
   {
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         _loc4_ = this.createItem(_loc3_);
         this.addItem(this.bag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function addToVAVList(oid)
   {
      var _loc2_ = this.createItem(oid);
      if(_loc2_)
      {
         this.addItem(this.visavisBarterList,_loc2_);
         lol.core.objects.ItemFactory.requestSD(oid);
      }
      this.vavReady = false;
   }
   function removeFromVAVList(oid)
   {
      var _loc2_ = this.visavisBarterList.getItem(oid);
      this.removeItem(this.visavisBarterList,_loc2_);
      this.vavReady = false;
   }
   function requestTranfer(transferObj)
   {
      var _loc4_;
      var _loc2_;
      var _loc5_;
      if(this.checkTransfer(transferObj))
      {
         this.iReady = false;
         _loc4_ = transferObj.item.id;
         if(transferObj.to == this.myBarterList)
         {
            _loc2_ = lol.core.player.Barter.UPD_TO_BUFFER;
         }
         else if(transferObj.to == this.bag)
         {
            _loc2_ = lol.core.player.Barter.UPD_TO_BAG;
         }
         _loc5_ = new lol.server.mess.CSM_SSUpdate(_loc2_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc4_)));
         if(this.XMC.Send(_loc5_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.transferAck);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function checkUse(transferObj)
   {
      if(transferObj.item instanceof lol.core.objects.Heapable && transferObj.hitted instanceof lol.core.objects.Heapable)
      {
         if(transferObj.item.typeID == transferObj.hitted.typeID)
         {
            this.joinHeap(lol.core.objects.Heapable(transferObj.item),lol.core.objects.Heapable(transferObj.hitted));
            this.removeItem(transferObj.from,transferObj.item);
            transferObj.to = null;
            this.applyTransfer(false);
            return true;
         }
      }
      return false;
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      this.__applyTransfer(succes,_loc2_);
      if(succes)
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
   }
   function ss_propose(id)
   {
      this.dialogPan = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = this.dialogPan.content;
      var _loc4_ = this.master.getPlayer(id);
      var _loc5_ = _loc4_.playerInfo;
      var _loc3_ = _loc5_.name;
      _loc2_.label = "Предложить бартер " + _loc3_ + "?";
      _loc2_.clickEvent = "proposeBarter";
      _loc2_.addEventListener("proposeBarter",this);
      this.visavisID = id;
   }
   function proposeBarter(obj)
   {
      lol.core.SceneShifter.closeWindow("query");
      var _loc3_;
      var _loc2_;
      if(obj.success)
      {
         _loc3_ = new lol.server.mess.CSM_SSCreate(lol.core.player.StuffManager.SESSION_BARTER,this.visavisID);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.proposeBarterAck);
         }
         this.alertPan = lol.core.SceneShifter.openNewWindow("alert");
         _loc2_ = this.alertPan.content;
         _loc2_.label = "Отказаться от бартера";
         _loc2_.clickEvent = "awaitingAnswer";
         _loc2_.addEventListener("awaitingAnswer",this);
      }
      else
      {
         this.kill();
      }
   }
   function awaitingAnswer(obj)
   {
      obj.target.removeEventListener("awaitingAnswer",this);
      lol.core.SceneShifter.closeWindow("alert");
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Barter.UPD_DENY,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      this.XMC.Send(_loc2_);
   }
   function proposeBarterAck(obj)
   {
      var _loc2_ = obj.param.res;
      var _loc3_;
      var _loc4_;
      if(_loc2_ != 0)
      {
         _loc3_ = this.alertPan.content;
         _loc3_.label = "Невозможно совершить бартер " + _loc2_;
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeWindow,1000,"alert");
      }
   }
   function ss_create(obj)
   {
      this.dialogPan = lol.core.SceneShifter.openNewAlert("topQuery");
      var _loc2_ = this.dialogPan;
      var _loc4_ = this.master.getPlayer(obj.param.target);
      var _loc5_ = _loc4_.playerInfo;
      var _loc3_ = _loc5_.name;
      _loc2_.label = _loc3_ + " предлагает бартер";
      _loc2_.clickEvent = "agreeBarter";
      _loc2_.addEventListener("agreeBarter",this);
      this.visavisID = obj.param.target;
      clearInterval(this.awaitingAnswerInt);
   }
   function agreeBarter(obj)
   {
      obj.target.removeEventListener("agreeBarter",this);
      lol.core.SceneShifter.closeAlert("query");
      var _loc2_;
      if(obj.success)
      {
         _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Barter.UPD_AGREE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.agreeBarterAck);
         }
      }
      else
      {
         this.denyBarter();
      }
   }
   function agreeBarterAck(obj)
   {
      this.createSession();
   }
   function denyBarter()
   {
      lol.core.SceneShifter.closeAlert();
      clearInterval(this.awaitingAnswerInt);
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Barter.UPD_DENY,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      this.XMC.Send(_loc2_);
   }
   function denyBarterAck(obj)
   {
      var _loc2_;
      var _loc5_;
      var _loc3_;
      var _loc4_;
      if(this.alertPan == undefined)
      {
         _loc2_ = this.dialogPan;
         _loc2_.removeEventListener("agreeBarter",this);
         _loc2_.label = "Игрок занят";
         _loc5_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,1000,"query");
      }
      else
      {
         _loc3_ = this.alertPan.content;
         _loc3_.label = "Игрок занят";
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeWindow,1000,"alert");
      }
   }
   function ss_upd(obj)
   {
      var _loc2_ = obj.param.s_status;
      var _loc4_ = obj.param.obj;
      if(_loc2_ == lol.core.player.Barter.UPD_CLOSE)
      {
         this.close(obj);
      }
      if(_loc2_ == lol.core.player.Barter.UPD_AGREE)
      {
         this.createSession();
      }
      if(_loc2_ == lol.core.player.Barter.UPD_DENY)
      {
         this.denyBarterAck();
      }
      if(_loc2_ == lol.core.player.Barter.UPD_TO_BUFFER)
      {
         this.addToVAVList(_loc4_);
      }
      if(_loc2_ == lol.core.player.Barter.UPD_TO_BAG)
      {
         this.removeFromVAVList(_loc4_);
      }
      if(_loc2_ == lol.core.player.Barter.UPD_APPLY)
      {
         this.vavReady = true;
      }
      if(_loc2_ == lol.core.player.Barter.UPD_BREAK)
      {
         this.vavReady = false;
      }
      if(_loc2_ == lol.core.player.Barter.UPD_ADD_AFRO)
      {
         this.visavisAddMoney(obj);
      }
      if(_loc2_ == lol.core.player.Barter.UPD_ADD_GOLD)
      {
         this.visavisAddMoney(obj);
      }
   }
   function close(obj)
   {
      var _loc2_;
      if(!obj)
      {
         _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Barter.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
         this.XMC.Send(_loc2_);
         this.returnBarterStuff();
      }
      this.denyBarterAck();
      this.dispatchEvent({type:"close"});
      this.kill();
   }
   function readyToBarter(ready)
   {
      this.iReady = ready;
      var _loc2_;
      if(ready)
      {
         _loc2_ = lol.core.player.Barter.UPD_APPLY;
      }
      else
      {
         _loc2_ = lol.core.player.Barter.UPD_BREAK;
      }
      var _loc3_ = new lol.server.mess.CSM_SSUpdate(_loc2_,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      this.XMC.Send(_loc3_);
      this.checkReady();
   }
   function set iReady(r)
   {
      this.__iReady = r;
      if(!r)
      {
         this.__vavReady = false;
      }
      this.checkReady();
   }
   function get iReady()
   {
      return this.__iReady;
   }
   function set vavReady(r)
   {
      this.__vavReady = r;
      if(!r)
      {
         this.__iReady = false;
      }
      this.checkReady();
   }
   function get vavReady()
   {
      return this.__vavReady;
   }
   function checkReady()
   {
      if(this.iReady && this.vavReady)
      {
         this.applyBarter();
      }
      this.dispatchEvent({type:"ready",i_ready:this.iReady,vav_ready:this.vavReady});
   }
   function applyBarter()
   {
      var _loc4_ = this.visavisBarterList.getItems();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = _loc4_[_loc2_];
         this.addItem(this.bag,_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      lol.core.SceneShifter.closeWindow("barter");
   }
   function returnBarterStuff()
   {
      var _loc4_ = this.myBarterList.getItems();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = _loc4_[_loc2_];
         this.addItem(this.bag,_loc3_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function addMoney(num, type)
   {
      var _loc3_;
      var _loc2_ = false;
      var _loc5_;
      var _loc6_;
      if(type == "afro")
      {
         _loc3_ = lol.core.player.Barter.UPD_ADD_AFRO;
         _loc5_ = lol.core.Master.getInstance().gamer.attributes.afro;
         if(num <= _loc5_)
         {
            _loc2_ = true;
         }
      }
      else if(type == "gold")
      {
         _loc3_ = lol.core.player.Barter.UPD_ADD_GOLD;
         _loc6_ = lol.core.Master.getInstance().gamer.attributes.gold;
         if(num <= _loc6_)
         {
            _loc2_ = true;
         }
      }
      var _loc7_;
      if(_loc2_)
      {
         this.moneyTransfer = new Object();
         this.moneyTransfer.num = num;
         this.moneyTransfer.type = type;
         _loc7_ = new lol.server.mess.CSM_SSUpdate(_loc3_,new lol.data.BigUINT(new lol.data.BigUINTCluster(num)));
         if(this.XMC.Send(_loc7_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.addMoneyAck);
         }
      }
      this.iReady = false;
   }
   function addMoneyAck(obj)
   {
      var _loc2_;
      if(obj.param.res == 0)
      {
         _loc2_ = true;
      }
      else
      {
         _loc2_ = false;
      }
      this.dispatchEvent({type:"myMUpdate",transfer:this.moneyTransfer,success:_loc2_});
   }
   function visavisAddMoney(obj)
   {
      var _loc2_ = obj.param.s_status;
      var _loc3_ = Number("0x" + obj.param.obj);
      var _loc4_;
      if(_loc2_ == lol.core.player.Barter.UPD_ADD_AFRO)
      {
         _loc4_ = "afro";
      }
      else if(_loc2_ == lol.core.player.Barter.UPD_ADD_GOLD)
      {
         _loc4_ = "gold";
      }
      this.vavReady = false;
      this.dispatchEvent({type:"visavisMUpdate",value:_loc3_,mtype:_loc4_});
   }
   function kill()
   {
      this.XMC.removeEventListener("ss_upd",this);
      lol.server.XMLCCallStack.skipCall("ss_ack",this,this.ss_ack);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.transferAck);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.transferAck);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      _loc3_.barter = null;
      super.kill();
   }
}
