class lol.core.player.Training
{
   var XMC;
   var alertPan;
   var dispatchEvent;
   var master;
   var visavisID;
   static var UPD_CLOSE = 0;
   static var UPD_FORGET = 1;
   static var UPD_LEARN = 2;
   function Training(visavisID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.master = lol.core.Master.getInstance();
      var _loc2_ = this.master.gamer;
   }
   function ss_propose(id)
   {
      var _loc2_ = lol.core.player.Teacher(this.master.getPlayer(id));
      var _loc3_ = _loc2_.playerInfo;
      var _loc5_ = _loc3_.name;
      this.visavisID = id;
      var _loc4_ = new lol.server.mess.CSM_SSCreate(lol.core.player.StuffManager.SESSION_TRAINING,this.visavisID);
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.proposeTrainingAck);
      }
   }
   function proposeTrainingAck(obj)
   {
      var _loc2_ = obj.param.res;
      var _loc3_;
      var _loc4_;
      if(_loc2_ == 0)
      {
         this.createSession();
      }
      else
      {
         _loc3_ = this.alertPan.content;
         _loc3_.label = "Невозможно начать обучение у " + _loc2_;
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeWindow,1000,"alert");
      }
   }
   function createSession()
   {
      lol.core.SceneShifter.closeWindow("query");
      lol.core.SceneShifter.closeWindow("alert");
      lol.core.player.NPCService.openService(this.visavisID);
   }
   function learn(spec)
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Training.UPD_LEARN,new lol.data.BigUINT(new lol.data.BigUINTCluster(spec)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.trainingAck);
      }
   }
   function forget(spec)
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Training.UPD_FORGET,new lol.data.BigUINT(new lol.data.BigUINTCluster(spec)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.trainingAck);
      }
   }
   function trainingAck(obj)
   {
   }
   function getCost()
   {
      var _loc7_ = this.master.gamer.attributes;
      var _loc5_ = _loc7_.specArray;
      var _loc8_ = _loc7_.max_specs;
      var _loc2_;
      var _loc6_ = _loc5_.length;
      var _loc4_ = 0;
      var _loc3_;
      _loc2_ = 0;
      while(_loc2_ < _loc6_)
      {
         _loc3_ = _loc5_[_loc2_];
         if(_loc3_.available)
         {
            _loc4_ = _loc4_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc9_;
      var _loc10_;
      if(_loc4_ < _loc8_)
      {
         _loc9_ = 0;
         _loc10_ = "afro";
      }
      else
      {
         switch(_loc4_)
         {
            case 0:
               _loc9_ = 0;
               _loc10_ = "afro";
               break;
            case 1:
               _loc9_ = 1000;
               _loc10_ = "afro";
               break;
            case 2:
               _loc9_ = 10;
               _loc10_ = "gold";
               break;
            case 3:
               _loc9_ = 30;
               _loc10_ = "gold";
               break;
            case 4:
               _loc9_ = 55;
               _loc10_ = "gold";
               break;
            default:
               _loc9_ = 75;
               _loc10_ = "gold";
         }
      }
      return {cost:_loc9_,type:_loc10_};
   }
   function close(obj)
   {
      var _loc2_;
      if(!obj)
      {
         obj.target.removeEventListener("close",this);
         _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Training.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
         this.XMC.Send(_loc2_);
      }
      this.dispatchEvent({type:"close"});
      lol.core.SceneShifter.linkGame.visavisAvatar.removeMovieClip();
      this.kill();
   }
   function kill()
   {
      var _loc2_ = this.master.gamer;
      _loc2_.training = null;
   }
}
