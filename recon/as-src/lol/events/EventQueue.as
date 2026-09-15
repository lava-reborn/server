class lol.events.EventQueue extends lol.events.EventBox
{
   var EventList;
   var addEventListener;
   var count;
   var dispatchEvent;
   var maxCount;
   var onBreak;
   var onComplete;
   var onContinue;
   var onEvent;
   var onEventDelegate;
   var onExecute;
   var onStart;
   var removeEventListener;
   var run;
   function EventQueue()
   {
      this.run = false;
      super.init(arguments);
      this.addEventListener("onStart",this);
      this.addEventListener("onBreak",this);
      this.addEventListener("onContinue",this);
      this.addEventListener("onComplete",this);
   }
   function Start(c, maxC)
   {
      if(!this.run)
      {
         this.run = true;
         this.setCount(c,maxC);
         this.Execute();
         this.dispatchEvent({type:"onStart",index:this.count});
      }
   }
   function Break()
   {
      this.run = false;
      clearInterval(this.EventList[this.count].interval);
      this.dispatchEvent({type:"onBreak",index:this.count});
   }
   function Continue()
   {
      this.run = true;
      this.Execute();
      this.dispatchEvent({type:"onContinue",index:this.count});
   }
   function Complete()
   {
      this.run = false;
      this.count = 0;
      for(var _loc2_ in this.EventList)
      {
         clearInterval(this.EventList[_loc2_].interval);
         this.EventList[_loc2_].removeEventListener("onEvent",this.onEventDelegate);
      }
      this.dispatchEvent({type:"onComplete"});
   }
   function Execute(i)
   {
      if(i)
      {
         this.count = i;
      }
      if(this.run)
      {
         super.Execute(this.count);
      }
   }
   function reportEvent(evt_obj)
   {
      super.reportEvent(evt_obj);
      this.count = this.count + 1;
      if(this.count > this.EventList.length - 1)
      {
         this.Complete();
      }
      else
      {
         this.Execute();
      }
   }
   function getCount()
   {
      return this.count;
   }
   function getMaxCount()
   {
      return this.maxCount;
   }
   function setCount(c, maxC)
   {
      if(typeof c === "number")
      {
         this.count = c;
      }
      else if(!this.count)
      {
         this.count = 0;
      }
      this.maxCount = !maxC ? this.EventList.length : maxC;
      if(this.maxCount >= this.EventList.length)
      {
         this.maxCount = this.EventList.length - 1;
      }
   }
   function kill()
   {
      this.removeEventListener("onExecute",this);
      this.removeEventListener("onEvent",this);
      this.removeEventListener("onStart",this);
      this.removeEventListener("onBreak",this);
      this.removeEventListener("onContinue",this);
      this.removeEventListener("onComplete",this);
      delete this.onExecute.target;
      delete this.onEvent.target;
      delete this.onStart.target;
      delete this.onBreak.target;
      delete this.onContinue.target;
      delete this.onComplete.target;
      delete this.onExecute.func;
      delete this.onEvent.func;
      delete this.onStart.func;
      delete this.onBreak.func;
      delete this.onContinue.func;
      delete this.onComplete.func;
      delete this.onExecute;
      delete this.onEvent;
      delete this.onStart;
      delete this.onBreak;
      delete this.onContinue;
      delete this.onComplete;
      delete this.onEventDelegate.target;
      delete this.onEventDelegate.func;
      delete this.onEventDelegate;
      this.clear();
   }
}
